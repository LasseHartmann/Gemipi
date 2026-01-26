"""GLaDOS eye display using Pygame."""

import math
import random
import threading
import time
from enum import Enum

try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False


class EyeState(Enum):
    """States for the eye animation."""
    IDLE = "idle"
    LISTENING = "listening"
    RESPONDING = "responding"
    BLINKING = "blinking"


class GLaDOSEye:
    """Animated GLaDOS eye display."""

    # Colors
    BACKGROUND = (0, 0, 0)
    EYE_ORANGE = (255, 150, 0)
    EYE_YELLOW = (255, 200, 50)
    EYE_CORE = (255, 255, 200)
    EYE_DIM = (180, 100, 0)
    APERTURE_GREY = (40, 40, 45)
    APERTURE_DARK = (20, 20, 25)

    def __init__(self, fullscreen: bool = True, width: int = 800, height: int = 480):
        """Initialize the eye display.

        Args:
            fullscreen: Run in fullscreen mode.
            width: Window width (ignored in fullscreen).
            height: Window height (ignored in fullscreen).
        """
        if not PYGAME_AVAILABLE:
            raise ImportError("Pygame is required for eye display. Install with: pip install pygame")

        self._fullscreen = fullscreen
        self._width = width
        self._height = height
        self._running = False
        self._state = EyeState.IDLE
        self._state_lock = threading.Lock()

        # Animation state
        self._pulse_phase = 0.0
        self._blink_timer = 0.0
        self._blink_duration = 0.0
        self._next_blink = random.uniform(3.0, 8.0)
        self._iris_size = 1.0
        self._target_iris_size = 1.0
        self._look_offset = [0.0, 0.0]
        self._target_look = [0.0, 0.0]
        self._aperture_rotation = 0.0

        # Thread for running display
        self._thread: threading.Thread | None = None
        self._screen = None
        self._clock = None

    def start(self) -> None:
        """Start the eye display in a separate thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the eye display."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

    def set_state(self, state: str) -> None:
        """Set the eye state from assistant state.

        Args:
            state: One of 'listening', 'responding', 'idle'
        """
        with self._state_lock:
            if state == "listening":
                self._state = EyeState.LISTENING
                self._target_iris_size = 1.1  # Slightly larger, attentive
            elif state == "responding":
                self._state = EyeState.RESPONDING
                self._target_iris_size = 0.9  # Focused
            else:
                self._state = EyeState.IDLE
                self._target_iris_size = 1.0

    def _run_loop(self) -> None:
        """Main display loop (runs in thread)."""
        pygame.init()

        if self._fullscreen:
            info = pygame.display.Info()
            self._width = info.current_w
            self._height = info.current_h
            self._screen = pygame.display.set_mode(
                (self._width, self._height),
                pygame.FULLSCREEN | pygame.HWSURFACE | pygame.DOUBLEBUF
            )
            pygame.mouse.set_visible(False)
        else:
            self._screen = pygame.display.set_mode((self._width, self._height))

        pygame.display.set_caption("GLaDOS")
        self._clock = pygame.time.Clock()

        last_time = time.time()

        while self._running:
            # Handle events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self._running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self._running = False

            # Calculate delta time
            current_time = time.time()
            dt = current_time - last_time
            last_time = current_time

            # Update animation
            self._update(dt)

            # Draw
            self._draw()

            pygame.display.flip()
            self._clock.tick(60)  # 60 FPS

        pygame.quit()

    def _update(self, dt: float) -> None:
        """Update animation state."""
        with self._state_lock:
            state = self._state

        # Pulse animation
        if state == EyeState.RESPONDING:
            self._pulse_phase += dt * 8.0  # Fast pulse when talking
        elif state == EyeState.LISTENING:
            self._pulse_phase += dt * 2.0  # Slow pulse when listening
        else:
            self._pulse_phase += dt * 1.0  # Very slow idle pulse

        # Iris size interpolation
        self._iris_size += (self._target_iris_size - self._iris_size) * dt * 5.0

        # Blinking
        self._blink_timer += dt
        if state == EyeState.BLINKING:
            if self._blink_timer >= self._blink_duration:
                with self._state_lock:
                    self._state = EyeState.IDLE
                self._next_blink = random.uniform(3.0, 8.0)
                self._blink_timer = 0.0
        else:
            if self._blink_timer >= self._next_blink and state == EyeState.IDLE:
                with self._state_lock:
                    self._state = EyeState.BLINKING
                self._blink_duration = random.uniform(0.1, 0.2)
                self._blink_timer = 0.0

        # Random look movement (only when idle)
        if state == EyeState.IDLE and random.random() < 0.01:
            self._target_look = [
                random.uniform(-0.2, 0.2),
                random.uniform(-0.1, 0.1)
            ]
        elif state != EyeState.IDLE:
            self._target_look = [0.0, 0.0]  # Look straight when active

        self._look_offset[0] += (self._target_look[0] - self._look_offset[0]) * dt * 2.0
        self._look_offset[1] += (self._target_look[1] - self._look_offset[1]) * dt * 2.0

        # Aperture rotation
        if state == EyeState.RESPONDING:
            self._aperture_rotation += dt * 30.0  # Rotate when talking
        else:
            self._aperture_rotation += dt * 5.0  # Slow rotation

    def _draw(self) -> None:
        """Draw the GLaDOS eye."""
        self._screen.fill(self.BACKGROUND)

        cx = self._width // 2
        cy = self._height // 2
        base_radius = min(self._width, self._height) // 3

        with self._state_lock:
            state = self._state

        # Calculate pulse intensity
        pulse = (math.sin(self._pulse_phase) + 1.0) / 2.0

        if state == EyeState.RESPONDING:
            intensity = 0.7 + pulse * 0.3
        elif state == EyeState.LISTENING:
            intensity = 0.5 + pulse * 0.3
        else:
            intensity = 0.3 + pulse * 0.2

        # Draw aperture blades (background)
        self._draw_aperture(cx, cy, base_radius * 1.2)

        # Blink effect
        if state == EyeState.BLINKING:
            blink_progress = self._blink_timer / self._blink_duration
            if blink_progress < 0.5:
                squish = 1.0 - (blink_progress * 2.0)
            else:
                squish = (blink_progress - 0.5) * 2.0
        else:
            squish = 1.0

        # Apply look offset
        look_x = int(self._look_offset[0] * base_radius * 0.3)
        look_y = int(self._look_offset[1] * base_radius * 0.3)

        # Draw outer glow
        glow_color = self._lerp_color(self.EYE_DIM, self.EYE_ORANGE, intensity)
        for i in range(5, 0, -1):
            alpha = int(50 * intensity * (i / 5))
            glow_surf = pygame.Surface((base_radius * 3, base_radius * 3), pygame.SRCALPHA)
            glow_r = int(base_radius * (1.0 + i * 0.1) * self._iris_size)
            pygame.draw.ellipse(
                glow_surf,
                (*glow_color, alpha),
                (
                    base_radius * 1.5 - glow_r,
                    base_radius * 1.5 - int(glow_r * squish),
                    glow_r * 2,
                    int(glow_r * 2 * squish)
                )
            )
            self._screen.blit(
                glow_surf,
                (cx - base_radius * 1.5 + look_x, cy - base_radius * 1.5 + look_y)
            )

        # Draw main eye
        eye_radius = int(base_radius * self._iris_size)
        eye_color = self._lerp_color(self.EYE_DIM, self.EYE_ORANGE, intensity)
        pygame.draw.ellipse(
            self._screen,
            eye_color,
            (
                cx - eye_radius + look_x,
                cy - int(eye_radius * squish) + look_y,
                eye_radius * 2,
                int(eye_radius * 2 * squish)
            )
        )

        # Draw inner bright ring
        inner_radius = int(eye_radius * 0.7)
        inner_color = self._lerp_color(self.EYE_ORANGE, self.EYE_YELLOW, intensity)
        pygame.draw.ellipse(
            self._screen,
            inner_color,
            (
                cx - inner_radius + look_x,
                cy - int(inner_radius * squish) + look_y,
                inner_radius * 2,
                int(inner_radius * 2 * squish)
            )
        )

        # Draw core (brightest center)
        core_radius = int(eye_radius * 0.3)
        core_color = self._lerp_color(self.EYE_YELLOW, self.EYE_CORE, intensity)
        pygame.draw.ellipse(
            self._screen,
            core_color,
            (
                cx - core_radius + look_x,
                cy - int(core_radius * squish) + look_y,
                core_radius * 2,
                int(core_radius * 2 * squish)
            )
        )

        # Draw pupil (dark center)
        pupil_radius = int(eye_radius * 0.1)
        pygame.draw.ellipse(
            self._screen,
            self.BACKGROUND,
            (
                cx - pupil_radius + look_x,
                cy - int(pupil_radius * squish) + look_y,
                pupil_radius * 2,
                int(pupil_radius * 2 * squish)
            )
        )

    def _draw_aperture(self, cx: int, cy: int, radius: float) -> None:
        """Draw the aperture blades around the eye."""
        num_blades = 8
        blade_width = 0.6  # Fraction of segment

        for i in range(num_blades):
            angle = (i / num_blades) * 2 * math.pi + math.radians(self._aperture_rotation)
            next_angle = angle + (blade_width / num_blades) * 2 * math.pi

            # Inner and outer radius
            r_inner = radius * 0.9
            r_outer = radius * 1.5

            points = [
                (cx + math.cos(angle) * r_inner, cy + math.sin(angle) * r_inner),
                (cx + math.cos(angle) * r_outer, cy + math.sin(angle) * r_outer),
                (cx + math.cos(next_angle) * r_outer, cy + math.sin(next_angle) * r_outer),
                (cx + math.cos(next_angle) * r_inner, cy + math.sin(next_angle) * r_inner),
            ]

            pygame.draw.polygon(self._screen, self.APERTURE_GREY, points)
            pygame.draw.polygon(self._screen, self.APERTURE_DARK, points, 2)

    def _lerp_color(self, c1: tuple, c2: tuple, t: float) -> tuple:
        """Linearly interpolate between two colors."""
        return (
            int(c1[0] + (c2[0] - c1[0]) * t),
            int(c1[1] + (c2[1] - c1[1]) * t),
            int(c1[2] + (c2[2] - c1[2]) * t),
        )


class JARVISEye:
    """Animated JARVIS holographic display."""

    # Colors - Blue holographic theme
    BACKGROUND = (0, 0, 0)
    BLUE_BRIGHT = (100, 200, 255)
    BLUE_MID = (50, 150, 220)
    BLUE_DIM = (20, 80, 140)
    BLUE_CORE = (200, 240, 255)
    BLUE_GLOW = (30, 100, 180)

    def __init__(self, fullscreen: bool = True, width: int = 800, height: int = 480):
        """Initialize the JARVIS display."""
        if not PYGAME_AVAILABLE:
            raise ImportError("Pygame is required for eye display. Install with: pip install pygame")

        self._fullscreen = fullscreen
        self._width = width
        self._height = height
        self._running = False
        self._state = EyeState.IDLE
        self._state_lock = threading.Lock()

        # Animation state
        self._pulse_phase = 0.0
        self._ring_rotation = [0.0, 0.0, 0.0]  # Multiple rings at different speeds
        self._arc_rotation = 0.0
        self._data_offset = 0.0

        # Thread for running display
        self._thread: threading.Thread | None = None
        self._screen = None
        self._clock = None

    def start(self) -> None:
        """Start the eye display in a separate thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the eye display."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

    def set_state(self, state: str) -> None:
        """Set the eye state from assistant state."""
        with self._state_lock:
            if state == "listening":
                self._state = EyeState.LISTENING
            elif state == "responding":
                self._state = EyeState.RESPONDING
            else:
                self._state = EyeState.IDLE

    def _run_loop(self) -> None:
        """Main display loop (runs in thread)."""
        pygame.init()

        if self._fullscreen:
            info = pygame.display.Info()
            self._width = info.current_w
            self._height = info.current_h
            self._screen = pygame.display.set_mode(
                (self._width, self._height),
                pygame.FULLSCREEN | pygame.HWSURFACE | pygame.DOUBLEBUF
            )
            pygame.mouse.set_visible(False)
        else:
            self._screen = pygame.display.set_mode((self._width, self._height))

        pygame.display.set_caption("JARVIS")
        self._clock = pygame.time.Clock()

        last_time = time.time()

        while self._running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self._running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self._running = False

            current_time = time.time()
            dt = current_time - last_time
            last_time = current_time

            self._update(dt)
            self._draw()

            pygame.display.flip()
            self._clock.tick(60)

        pygame.quit()

    def _update(self, dt: float) -> None:
        """Update animation state."""
        with self._state_lock:
            state = self._state

        # Pulse animation
        if state == EyeState.RESPONDING:
            self._pulse_phase += dt * 6.0
            rotation_speed = 2.0
        elif state == EyeState.LISTENING:
            self._pulse_phase += dt * 3.0
            rotation_speed = 1.0
        else:
            self._pulse_phase += dt * 1.5
            rotation_speed = 0.5

        # Ring rotations (different speeds, different directions)
        self._ring_rotation[0] += dt * 20.0 * rotation_speed
        self._ring_rotation[1] -= dt * 15.0 * rotation_speed
        self._ring_rotation[2] += dt * 25.0 * rotation_speed

        # Arc segments rotation
        self._arc_rotation += dt * 40.0 * rotation_speed

        # Data stream offset
        self._data_offset += dt * 100.0

    def _draw(self) -> None:
        """Draw the JARVIS holographic interface."""
        self._screen.fill(self.BACKGROUND)

        cx = self._width // 2
        cy = self._height // 2
        base_radius = min(self._width, self._height) // 3

        with self._state_lock:
            state = self._state

        # Calculate pulse intensity
        pulse = (math.sin(self._pulse_phase) + 1.0) / 2.0

        if state == EyeState.RESPONDING:
            intensity = 0.7 + pulse * 0.3
        elif state == EyeState.LISTENING:
            intensity = 0.5 + pulse * 0.3
        else:
            intensity = 0.3 + pulse * 0.2

        # Draw outer glow
        self._draw_glow(cx, cy, base_radius, intensity)

        # Draw concentric rings
        self._draw_rings(cx, cy, base_radius, intensity)

        # Draw arc segments
        self._draw_arcs(cx, cy, base_radius, intensity)

        # Draw center core
        self._draw_core(cx, cy, base_radius, intensity)

        # Draw data lines
        self._draw_data_lines(cx, cy, base_radius, intensity)

    def _draw_glow(self, cx: int, cy: int, radius: float, intensity: float) -> None:
        """Draw the outer glow effect."""
        for i in range(8, 0, -1):
            alpha = int(20 * intensity * (i / 8))
            glow_surf = pygame.Surface((radius * 4, radius * 4), pygame.SRCALPHA)
            glow_r = int(radius * (1.0 + i * 0.15))
            pygame.draw.circle(
                glow_surf,
                (*self.BLUE_GLOW, alpha),
                (int(radius * 2), int(radius * 2)),
                glow_r
            )
            self._screen.blit(glow_surf, (cx - radius * 2, cy - radius * 2))

    def _draw_rings(self, cx: int, cy: int, radius: float, intensity: float) -> None:
        """Draw concentric rotating rings."""
        ring_radii = [0.95, 0.75, 0.55]
        ring_widths = [3, 2, 2]

        for i, (r_mult, width) in enumerate(zip(ring_radii, ring_widths)):
            r = int(radius * r_mult)
            color = self._lerp_color(self.BLUE_DIM, self.BLUE_MID, intensity)

            # Draw dashed circle
            num_dashes = 36
            dash_length = 0.7  # Fraction of segment

            for j in range(num_dashes):
                start_angle = (j / num_dashes) * 2 * math.pi + math.radians(self._ring_rotation[i])
                end_angle = start_angle + (dash_length / num_dashes) * 2 * math.pi

                # Draw arc
                rect = pygame.Rect(cx - r, cy - r, r * 2, r * 2)
                pygame.draw.arc(self._screen, color, rect, start_angle, end_angle, width)

    def _draw_arcs(self, cx: int, cy: int, radius: float, intensity: float) -> None:
        """Draw rotating arc segments."""
        color = self._lerp_color(self.BLUE_MID, self.BLUE_BRIGHT, intensity)

        # Outer arc segments
        num_arcs = 4
        arc_length = math.pi / 6  # 30 degrees each

        for i in range(num_arcs):
            base_angle = (i / num_arcs) * 2 * math.pi + math.radians(self._arc_rotation)

            r = int(radius * 1.1)
            rect = pygame.Rect(cx - r, cy - r, r * 2, r * 2)
            pygame.draw.arc(self._screen, color, rect, base_angle, base_angle + arc_length, 4)

        # Inner arc segments (opposite direction)
        for i in range(num_arcs):
            base_angle = (i / num_arcs) * 2 * math.pi - math.radians(self._arc_rotation * 0.7)

            r = int(radius * 0.4)
            rect = pygame.Rect(cx - r, cy - r, r * 2, r * 2)
            pygame.draw.arc(self._screen, color, rect, base_angle, base_angle + arc_length, 3)

    def _draw_core(self, cx: int, cy: int, radius: float, intensity: float) -> None:
        """Draw the center core."""
        # Core glow
        core_color = self._lerp_color(self.BLUE_MID, self.BLUE_CORE, intensity)
        core_radius = int(radius * 0.2)

        # Outer core ring
        pygame.draw.circle(self._screen, core_color, (cx, cy), core_radius, 2)

        # Inner filled core
        inner_radius = int(core_radius * 0.6)
        inner_color = self._lerp_color(self.BLUE_BRIGHT, self.BLUE_CORE, intensity)
        pygame.draw.circle(self._screen, inner_color, (cx, cy), inner_radius)

        # Center dot
        pygame.draw.circle(self._screen, self.BLUE_CORE, (cx, cy), 3)

    def _draw_data_lines(self, cx: int, cy: int, radius: float, intensity: float) -> None:
        """Draw scrolling data/text lines effect."""
        color = self._lerp_color(self.BLUE_DIM, self.BLUE_MID, intensity * 0.5)

        # Horizontal data lines
        line_spacing = 20
        line_width = int(radius * 0.3)

        for i in range(-3, 4):
            if i == 0:
                continue
            y = cy + i * line_spacing

            # Create varying line segments
            offset = int(self._data_offset + i * 50) % 100
            x_start = cx + int(radius * 0.5) + offset - 50
            x_end = x_start + line_width

            # Clip to screen
            if x_start < cx + radius * 1.2 and x_end > cx + radius * 0.4:
                pygame.draw.line(self._screen, color, (x_start, y), (x_end, y), 1)

            # Mirror on left side
            x_start_l = cx - int(radius * 0.5) - offset + 50 - line_width
            x_end_l = x_start_l + line_width

            if x_end_l > cx - radius * 1.2 and x_start_l < cx - radius * 0.4:
                pygame.draw.line(self._screen, color, (x_start_l, y), (x_end_l, y), 1)

    def _lerp_color(self, c1: tuple, c2: tuple, t: float) -> tuple:
        """Linearly interpolate between two colors."""
        return (
            int(c1[0] + (c2[0] - c1[0]) * t),
            int(c1[1] + (c2[1] - c1[1]) * t),
            int(c1[2] + (c2[2] - c1[2]) * t),
        )


def create_eye_display(personality: str, fullscreen: bool = True) -> GLaDOSEye | JARVISEye:
    """Factory function to create the appropriate eye display for a personality.

    Args:
        personality: Personality name ('glados', 'jarvis', etc.)
        fullscreen: Run in fullscreen mode.

    Returns:
        Eye display instance for the personality.
    """
    if personality.lower() == "jarvis":
        return JARVISEye(fullscreen=fullscreen)
    else:
        # Default to GLaDOS eye
        return GLaDOSEye(fullscreen=fullscreen)
