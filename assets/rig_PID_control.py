import omni
import omni.kit.app
import omni.appwindow
import carb
import numpy as np
from pxr import UsdGeom, UsdPhysics, Gf
import omni.physx.scripts.physicsUtils as physx_utils

# ============================================================
# ⚠️ MOTOR CONSTANTS - VOLTAGE CONFIGURATION
# ============================================================

MOTOR_RPM_RATED = 16000          # RPM at rated voltage
MOTOR_VOLTAGE_RATED = 3.7        # Rated motor voltage (V)
MOTOR_THRUST_RATED = 11.5        # Thrust at rated RPM (grams)
L298N_VOLTAGE_DROP = 2.0         # L298N driver voltage drop (V)

# ⚠️ KEY FIX: Increase motor voltage for more thrust!
# Options: 3.7V (rated), 4.0V (safe), 5.0V (ok), 6.0V (max from L298N)
MOTOR_VOLTAGE_MAX = 5.0          # ← CHANGE THIS for more thrust!

# Thrust scales with voltage SQUARED: T_new = T_rated × (V_new/V_rated)²
THRUST_SCALE = (MOTOR_VOLTAGE_MAX / MOTOR_VOLTAGE_RATED) ** 2
MOTOR_THRUST_MAX = MOTOR_THRUST_RATED * THRUST_SCALE

K_V = MOTOR_RPM_RATED / MOTOR_VOLTAGE_RATED                    # RPM per volt (~4324)
K_T = MOTOR_THRUST_MAX / (MOTOR_RPM_RATED ** 2)                # Updated thrust constant

MOTOR_TIME_CONSTANT = 0.15

# ============================================================
# ROTOR DIRECTION CONFIGURATION
# ============================================================

ROTOR_LEFT_DIRECTION = 1.0    # +1 = CW
ROTOR_RIGHT_DIRECTION = -1.0  # -1 = CCW

RPM_STOP_THRESHOLD = 100.0

# ============================================================
# POWER SUPPLY
# ============================================================

class PowerSupplyConfig:

    def __init__(self, supply_voltage=9.0):

        self.v_supply = supply_voltage
        self.v_drop = L298N_VOLTAGE_DROP
        self.v_motor_max = MOTOR_VOLTAGE_MAX  # ← Use configurable max voltage

        self.duty_max = self._calculate_max_duty()
        self.duty_min = 0.0

    def _calculate_max_duty(self):

        v_effective_max = self.v_supply - self.v_drop

        if v_effective_max <= 0:
            return 0.0

        duty = self.v_motor_max / v_effective_max

        return min(1.0, max(0.0, duty))

    def clamp_duty(self, duty):

        return np.clip(duty, self.duty_min, self.duty_max)

    def get_effective_voltage(self, duty):

        duty = self.clamp_duty(duty)

        return (self.v_supply - self.v_drop) * duty

    def get_rpm(self, duty):

        return K_V * self.get_effective_voltage(duty)

    def get_thrust(self, duty):

        rpm = self.get_rpm(duty)

        return K_T * (rpm ** 2)

    def duty_from_thrust(self, thrust):

        if thrust <= 0:
            return 0.0

        denom = (self.v_supply - self.v_drop)

        if denom <= 0:
            return 0.0

        duty = np.sqrt(thrust / K_T) / (K_V * denom)

        return self.clamp_duty(duty)

# ============================================================
# STAGE
# ============================================================

stage = omni.usd.get_context().get_stage()

imu = stage.GetPrimAtPath("/bicopter/IMU_sensor/Imu_Sensor")

rotor_left = stage.GetPrimAtPath("/bicopter/rotor_left")
rotor_right = stage.GetPrimAtPath("/bicopter/rotor_right")

joint_left = stage.GetPrimAtPath("/bicopter/motor_left_to_rotor_left")
joint_right = stage.GetPrimAtPath("/bicopter/motor_right_to_rotor_right")

power_supply = PowerSupplyConfig(9.0)

# ============================================================
# ROTOR DRIVE INITIALIZATION
# ============================================================

def initialize_rotor_drive(joint):

    if not joint.IsValid():
        return

    drive = UsdPhysics.DriveAPI.Apply(joint, "angular")

    drive.GetStiffnessAttr().Set(10000.0)
    drive.GetDampingAttr().Set(1000.0)
    drive.GetMaxForceAttr().Set(10000.0)

initialize_rotor_drive(joint_left)
initialize_rotor_drive(joint_right)

# ============================================================
# ⚠️ FIX: PARAMETERS WITH HIGHER BASE THRUST
# ============================================================

class ControllerParams:

    def __init__(self):

        self.Kp = 0.0
        self.Kd = 0.0
        self.Ki = 0.0

        # ⚠️ FIX: Base thrust should be ~50% of max for headroom
        self.base_thrust = MOTOR_THRUST_MAX * 0.5

        self.max_thrust = MOTOR_THRUST_MAX
        self.min_thrust = 0.0

params = ControllerParams()

# ============================================================
# STATE
# ============================================================

prev_error = 0.0
integral_error = 0.0

left_motor_rpm = 0.0
right_motor_rpm = 0.0

left_rotor_angle = 0.0
right_rotor_angle = 0.0

controller_running = False
frame_count = 0

# ============================================================
# IMU PITCH IN DEGREES
# ============================================================

def get_pitch_degrees():

    imu_local = stage.GetPrimAtPath("/bicopter/IMU_sensor/Imu_Sensor")

    if not imu_local.IsValid():
        return 0.0

    xform = UsdGeom.Xformable(imu_local)

    mat = xform.ComputeLocalToWorldTransform(0)

    forward = mat.ExtractRotation().TransformDir((0, 0, 1))

    pitch_rad = np.arctan2(forward[1], forward[2])
    
    pitch_deg = np.degrees(pitch_rad)

    return pitch_deg

# ============================================================
# VISUAL ROTOR SPIN
# ============================================================

def rotate_visual(rotor, rpm, direction, current_angle):

    if not rotor.IsValid():
        return current_angle

    if rpm < RPM_STOP_THRESHOLD:
        return current_angle

    deg_per_sec = rpm * 6.0
    dt = 1.0 / 60.0
    angle_increment = direction * deg_per_sec * dt
    new_angle = current_angle + angle_increment

    xform = UsdGeom.Xformable(rotor)

    for op in xform.GetOrderedXformOps():
        if op.GetOpType() == UsdGeom.XformOp.TypeRotateZ:
            op.Set(new_angle)
            return new_angle

    rot_op = xform.AddRotateZOp()
    rot_op.Set(new_angle)

    return new_angle

# ============================================================
# ROTOR MOTOR
# ============================================================

def spin_rotor(joint, rpm, direction):

    if not joint.IsValid():
        return

    drive = UsdPhysics.DriveAPI.Apply(joint, "angular")

    if rpm < RPM_STOP_THRESHOLD:
        drive.GetTargetVelocityAttr().Set(0.0)
        return

    rad_s = rpm * (2.0 * np.pi / 60.0) * direction

    drive.GetTargetVelocityAttr().Set(rad_s)

# ============================================================
# THRUST
# ============================================================

def apply_thrust(rotor, thrust_grams):

    thrust_newton = thrust_grams * 0.00981

    if thrust_grams < 0.1:
        return

    physx_utils.add_force_torque(
        stage,
        rotor.GetPath(),
        force=Gf.Vec3f(0.0, 0.0, -thrust_newton),
        mode='force',
        isWorldSpace=True
    )

# ============================================================
# MOTOR DYNAMICS
# ============================================================

def update_motor(current_rpm, target_rpm, dt):

    alpha = dt / MOTOR_TIME_CONSTANT

    return current_rpm + alpha * (target_rpm - current_rpm)

# ============================================================
# ⚠️ FIX: CONTROLLER WITH ANTI-WINDUP & SATURATION
# ============================================================

# ============================================================
# ⚠️ FIX: CONTROLLER (Corrected PID Sign!)
# ============================================================

def controller():

    global prev_error
    global integral_error
    global left_motor_rpm
    global right_motor_rpm
    global left_rotor_angle
    global right_rotor_angle
    global frame_count

    pitch_deg = get_pitch_degrees()
    pitch_rad = np.radians(pitch_deg)

    # ⚠️ KEY FIX: Invert error sign!
    # When left side is DOWN (negative pitch), we need LEFT thrust to INCREASE
    error = -pitch_rad  # ← NEGATE THE ERROR!

    # ⚠️ FIX: Anti-windup for integral term
    if abs(error) < 0.5:  # Only integrate near equilibrium
        integral_error += error
    else:
        integral_error *= 0.95  # Decay integral when far from target

    derivative = error - prev_error

    control = params.Kp * error + params.Kd * derivative + params.Ki * integral_error

    prev_error = error

    left_thrust = params.base_thrust + control
    right_thrust = params.base_thrust - control

    left_thrust = np.clip(left_thrust, params.min_thrust, params.max_thrust)
    right_thrust = np.clip(right_thrust, params.min_thrust, params.max_thrust)

    left_duty = power_supply.duty_from_thrust(left_thrust)
    right_duty = power_supply.duty_from_thrust(right_thrust)

    cmd_left_rpm = power_supply.get_rpm(left_duty)
    cmd_right_rpm = power_supply.get_rpm(right_duty)

    dt = 1.0 / 60.0

    left_motor_rpm = update_motor(left_motor_rpm, cmd_left_rpm, dt)
    right_motor_rpm = update_motor(right_motor_rpm, cmd_right_rpm, dt)

    spin_rotor(joint_left, left_motor_rpm, ROTOR_LEFT_DIRECTION)
    spin_rotor(joint_right, right_motor_rpm, ROTOR_RIGHT_DIRECTION)

    left_rotor_angle = rotate_visual(rotor_left, left_motor_rpm, ROTOR_LEFT_DIRECTION, left_rotor_angle)
    right_rotor_angle = rotate_visual(rotor_right, right_motor_rpm, ROTOR_RIGHT_DIRECTION, right_rotor_angle)

    apply_thrust(rotor_left, left_thrust)
    apply_thrust(rotor_right, right_thrust)

    frame_count += 1

    if frame_count % 10 == 0:
        
        pitch_sign = "+" if pitch_deg >= 0 else ""
        thrust_diff = abs(left_thrust - right_thrust)
        
        # ⚠️ Show which motor should be lifting
        if pitch_deg < -45:
            status = "← LEFT SHOULD LIFT"
        elif pitch_deg > 45:
            status = "→ RIGHT SHOULD LIFT"
        else:
            status = "BALANCING"
        
        print(
        f"pitch:{pitch_sign}{pitch_deg:.2f}° [{status}] "
        f"L:{left_thrust:.2f}g@{left_motor_rpm:.0f}rpm "
        f"R:{right_thrust:.2f}g@{right_motor_rpm:.0f}rpm "
        f"ΔT:{thrust_diff:.2f}g "
        f"Kp:{params.Kp:.2f} Kd:{params.Kd:.2f}"
        )

# ============================================================
# UPDATE LOOP
# ============================================================

def update(step):

    if controller_running:
        controller()

sub = omni.kit.app.get_app().get_update_event_stream().create_subscription_to_pop(update)

# ============================================================
# KEYBOARD
# ============================================================

app_window = omni.appwindow.get_default_app_window()

def random_pid():

    params.Kp = np.random.uniform(-20, 20)
    params.Kd = np.random.uniform(-20, 20)

    print(f"\nAUTO TUNE → Kp={params.Kp:.3f}  Kd={params.Kd:.3f}\n")

def on_keyboard_event(event, *args):

    global controller_running

    if event.type in (carb.input.KeyboardEventType.KEY_PRESS, carb.input.KeyboardEventType.KEY_REPEAT):

        if event.input == carb.input.KeyboardInput.S:
            controller_running = True
            print("Controller STARTED")

        elif event.input == carb.input.KeyboardInput.X:
            controller_running = False
            print("Controller STOPPED")

        elif event.input == carb.input.KeyboardInput.SPACE:
            random_pid()

        elif event.input == carb.input.KeyboardInput.UP:
            params.Kp += 1
            print("Kp:", params.Kp)

        elif event.input == carb.input.KeyboardInput.DOWN:
            params.Kp -= 1
            print("Kp:", params.Kp)

        elif event.input == carb.input.KeyboardInput.RIGHT:
            params.Kd += 1
            print("Kd:", params.Kd)

        elif event.input == carb.input.KeyboardInput.LEFT:
            params.Kd -= 1
            print("Kd:", params.Kd)
        

keyboard = app_window.get_keyboard()

keyboard_sub = carb.input.acquire_input_interface().subscribe_to_keyboard_events(
    keyboard,
    on_keyboard_event
)

# ============================================================
# ⚠️ NEW: VOLTAGE CONFIGURATION FUNCTION
# ============================================================

def set_motor_voltage(voltage):
    """Change motor voltage and recalculate all constants"""
    global MOTOR_VOLTAGE_MAX, MOTOR_THRUST_MAX, K_T, params, power_supply
    
    MOTOR_VOLTAGE_MAX = voltage
    THRUST_SCALE = (MOTOR_VOLTAGE_MAX / MOTOR_VOLTAGE_RATED) ** 2
    MOTOR_THRUST_MAX = MOTOR_THRUST_RATED * THRUST_SCALE
    K_T = MOTOR_THRUST_MAX / (MOTOR_RPM_RATED ** 2)
    
    # Update power supply
    power_supply = PowerSupplyConfig(9.0)
    
    # Update controller params
    params.max_thrust = MOTOR_THRUST_MAX
    params.base_thrust = MOTOR_THRUST_MAX * 0.5
    
    print(f"\n⚡ VOLTAGE CHANGED TO {voltage}V")
    print(f"   Max Thrust: {MOTOR_THRUST_MAX:.2f}g ({THRUST_SCALE*100-100:+.1f}%)")
    print(f"   Max RPM: {K_V * voltage:.0f}")
    print(f"   Base Thrust: {params.base_thrust:.2f}g\n")

# ============================================================
# STARTUP MESSAGE
# ============================================================

print("\n" + "="*70)
print("BICOPTER CONTROLLER READY")
print("="*70)
print(f"Left Rotor (Bottom):  {'CW' if ROTOR_LEFT_DIRECTION > 0 else 'CCW'}")
print(f"Right Rotor (Top):    {'CW' if ROTOR_RIGHT_DIRECTION > 0 else 'CCW'}")
print(f"Thrust Direction:     -Z (downward → upward lift)")
print(f"RPM Stop Threshold:   {RPM_STOP_THRESHOLD:.0f} RPM")
print("="*70)
print("⚡ MOTOR VOLTAGE CONFIGURATION:")
print(f"   Current: {MOTOR_VOLTAGE_MAX}V")
print(f"   Max Thrust: {MOTOR_THRUST_MAX:.2f}g")
print(f"   Thrust Scale: {(MOTOR_THRUST_MAX/MOTOR_THRUST_RATED-1)*100:+.1f}% vs rated")
print("="*70)
print("KEYBOARD CONTROLS:")
print("  S         = start controller")
print("  X         = stop controller")
print("  SPACE     = random PID")
print("  ↑↓        = tune Kp (+/- 1)")
print("  ←→        = tune Kd (+/- 1)")
print("  1         = 3.7V (rated, 11.5g thrust)")
print("  2         = 4.0V (safe, 13.5g thrust)")
print("  3         = 5.0V (ok, 21.1g thrust)")
print("  4         = 6.0V (max, 30.4g thrust)")
print("="*70)
print("Pitch Display:")
print("  +XX.XX° = Right side down (CW rotation)")
print("  -XX.XX° = Left side down (CCW rotation)")
print("  0.00°   = Level (balanced)")
print("="*70 + "\n")