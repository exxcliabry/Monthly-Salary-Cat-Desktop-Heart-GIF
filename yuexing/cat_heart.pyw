"""
月薪猫爱心小程序 - pygame版本
从底部逐个生成，逆时针形成爱心
真正的透明图层叠加，无遮挡问题
"""

import pygame
import math
import os
import random
import sys

# ============================================================
#  配置参数
# ============================================================
CONFIG = {
    "total_actions": 1,
    "cat_size": 200,
    "giant_cat_size": 1000,
    "heart_scale": 20,
    "outline_count": 15,
    "screen_width": 1700,
    "screen_height": 1650,
    "gif_fps": 0,             # GIF播放帧率（0=使用GIF自带帧延迟）
    "spawn_interval": 120,    # 生成间隔（毫秒）
    "black_threshold": 35,    # 抠图阈值
    "gif_brightness": 1.5,    # GIF亮度（1.0=原始，>1更亮，<1更暗）
}


def remove_bg_surface(surface, threshold=40):
    """
    抠图：将接近黑色的像素变为透明
    """
    surface = surface.convert_alpha()
    pixels = pygame.surfarray.pixels3d(surface)
    alpha = pygame.surfarray.pixels_alpha(surface)

    # 计算与黑色的差异
    black_diff = pixels.sum(axis=2)

    # 设置透明度
    alpha[black_diff < threshold * 3] = 10

    # 边缘半透明
    mask = (black_diff >= threshold * 3) & (black_diff < threshold * 6)
    alpha[mask] = ((black_diff[mask] - threshold * 3) / (threshold * 3) * 255).astype(alpha.dtype)

    del pixels
    del alpha

    return surface


class AnimatedCat:
    """单个动画猫咪"""

    def __init__(self, gif_path, x, y, size, threshold, brightness=1.0):
        self.x = x
        self.y = y
        self.frames = []
        self.frame_delays = []   # 每帧延迟（毫秒）
        self.anim_start = 0      # 动画起始时间
        self.started = False

        # 加载GIF所有帧
        self.load_gif(gif_path, size, threshold, brightness)

    def load_gif(self, gif_path, size, threshold, brightness=1.0):
        """加载GIF并抠图，同时提取帧延迟"""
        try:
            from PIL import Image, ImageEnhance

            img = Image.open(gif_path)
            frame_count = getattr(img, 'n_frames', 1)

            for i in range(frame_count):
                img.seek(i)
                frame = img.copy().convert("RGBA")
                frame = frame.resize((size, size), Image.Resampling.LANCZOS)

                # 提取帧延迟
                delay = img.info.get('duration', 0)
                self.frame_delays.append(delay)

                # 调整亮度
                if brightness != 1.0:
                    enhancer = ImageEnhance.Brightness(frame)
                    frame = enhancer.enhance(brightness)

                # PIL转pygame surface
                raw = frame.tobytes()
                surface = pygame.image.fromstring(raw, frame.size, "RGBA")

                # 抠图
                surface = remove_bg_surface(surface, threshold)
                self.frames.append(surface)

            # 规范化延迟：0或过短的用100ms，上限500ms
            self.frame_delays = [
                max(20, min(d if d > 0 else 100, 500))
                for d in self.frame_delays
            ]

        except Exception as e:
            print(f"加载失败 {gif_path}: {e}")

    def update(self, current_time):
        """启动动画计时"""
        if not self.started and self.frames:
            self.anim_start = current_time
            self.started = True

    def get_frame_index(self, current_time):
        """基于绝对时间计算当前帧索引，掉帧不卡"""
        if not self.frames:
            return 0
        elapsed = current_time - self.anim_start
        total_duration = sum(self.frame_delays)
        if total_duration > 0:
            elapsed %= total_duration
        total_time = 0
        for i, delay in enumerate(self.frame_delays):
            total_time += delay
            if elapsed < total_time:
                return i
        return 0

    def draw(self, screen, current_time):
        """绘制当前帧"""
        if self.frames:
            idx = self.get_frame_index(current_time)
            frame = self.frames[idx]
            rect = frame.get_rect(center=(self.x, self.y))
            screen.blit(frame, rect)


class CatHeartApp:
    def __init__(self):
        pygame.init()

        # 设置显示模式：无边框 + 透明
        self.screen = pygame.display.set_mode(
            (CONFIG["screen_width"], CONFIG["screen_height"]),
            pygame.NOFRAME
        )
        pygame.display.set_caption("月薪猫爱心")

        # 设置窗口透明（Windows）
        self.set_window_transparent()

        # 居中窗口
        self.center_window()

        # 中心点
        self.center_x = CONFIG["screen_width"] // 2
        self.center_y = CONFIG["screen_height"] // 2 + 20

        # 猫咪列表
        self.cats = []
        self.spawn_index = 0
        self.heart_points = []
        self.last_spawn_time = 0
        self.disappear_index = 0

        # 预加载GIF
        self.gif_paths = []
        for i in range(1, CONFIG["total_actions"] + 1):
            path = f"{i}.gif"
            if os.path.exists(path):
                self.gif_paths.append(path)

        # 预加载大猫高清帧（500px），运行时smoothscale缩放保证画质
        self.giant_frames = []
        self.giant_frame_delays = []
        self.giant_anim_start = 0
        if self.gif_paths:
            self.preload_giant_frames()

        # 生成爱心点
        self.heart_points = self.get_heart_points()

        # 字体
        pygame.font.init()
        self.font = pygame.font.SysFont("microsoftyahei", 20)

    def set_window_transparent(self):
        """设置窗口透明（Windows API）"""
        try:
            import ctypes
            hwnd = pygame.display.get_wm_info()["window"]

            # 设置窗口分层
            style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
            style |= 0x00080000  # WS_EX_LAYERED
            ctypes.windll.user32.SetWindowLongW(hwnd, -20, style)

            # 设置透明色（黑色）
            ctypes.windll.user32.SetLayeredWindowAttributes(
                hwnd, 0x000000, 0, 0x00000001  # LWA_COLORKEY
            )
        except Exception as e:
            print(f"透明设置失败: {e}")

    def center_window(self):
        """窗口居中"""
        import ctypes
        user32 = ctypes.windll.user32
        screen_w = user32.GetSystemMetrics(0)
        screen_h = user32.GetSystemMetrics(1)
        x = (screen_w - CONFIG["screen_width"]) // 2
        y = (screen_h - CONFIG["screen_height"]) // 2
        os.environ['SDL_VIDEO_WINDOW_POS'] = f"{x},{y}"

    def preload_giant_frames(self):
        """预加载大猫高清帧"""
        try:
            from PIL import Image, ImageEnhance
            path = random.choice(self.gif_paths)
            img = Image.open(path)
            frame_count = getattr(img, 'n_frames', 1)
            size = CONFIG["giant_cat_size"]
            brightness = CONFIG["gif_brightness"]

            for i in range(frame_count):
                img.seek(i)
                frame = img.copy().convert("RGBA")
                frame = frame.resize((size, size), Image.Resampling.LANCZOS)

                # 提取帧延迟
                delay = img.info.get('duration', 0)
                self.giant_frame_delays.append(delay)

                # 调整亮度
                if brightness != 1.0:
                    enhancer = ImageEnhance.Brightness(frame)
                    frame = enhancer.enhance(brightness)

                raw = frame.tobytes()
                surface = pygame.image.fromstring(raw, frame.size, "RGBA")
                surface = remove_bg_surface(surface, CONFIG["black_threshold"])
                self.giant_frames.append(surface)

            # 规范化延迟
            self.giant_frame_delays = [
                max(20, min(d if d > 0 else 100, 500))
                for d in self.giant_frame_delays
            ]
        except Exception as e:
            print(f"大猫帧加载失败: {e}")

    def draw_giant_cat(self, screen, current_time, current_size):
        """绘制指定尺寸的大猫（从高清帧缩放）"""
        if not self.giant_frames:
            return
        # 首次绘制时记录动画起始时间
        if self.giant_anim_start == 0:
            self.giant_anim_start = current_time
        # 基于时间计算当前帧
        elapsed = current_time - self.giant_anim_start
        total_duration = sum(self.giant_frame_delays)
        if total_duration > 0:
            elapsed %= total_duration
        total_time = 0
        frame_idx = 0
        for i, delay in enumerate(self.giant_frame_delays):
            total_time += delay
            if elapsed < total_time:
                frame_idx = i
                break
        # 从高清帧smoothscale到当前尺寸
        frame = self.giant_frames[frame_idx]
        scaled = pygame.transform.smoothscale(frame, (int(current_size), int(current_size)))
        rect = scaled.get_rect(center=(self.center_x, self.center_y))
        screen.blit(scaled, rect)

    def heart_x(self, t):
        return 16 * math.pow(math.sin(t), 3)

    def heart_y(self, t):
        return -(13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t))

    def get_heart_points(self):
        """获取爱心轮廓点（从底部逆时针，弧长均匀采样）"""
        count = CONFIG["outline_count"]
        scale = CONFIG["heart_scale"]
        start_t = math.pi * 1.5

        # 密集采样以计算弧长
        dense_count = 500
        dense_points = []
        for i in range(dense_count):
            t = start_t - (i / dense_count) * 2 * math.pi
            x = self.heart_x(t) * scale + self.center_x
            y = self.heart_y(t) * scale + self.center_y
            dense_points.append((x, y))

        # 计算累积弧长
        cum_len = [0.0]
        for i in range(1, len(dense_points)):
            dx = dense_points[i][0] - dense_points[i - 1][0]
            dy = dense_points[i][1] - dense_points[i - 1][1]
            cum_len.append(cum_len[-1] + math.sqrt(dx * dx + dy * dy))

        total_len = cum_len[-1]

        # 按弧长等距采样
        points = []
        for i in range(count):
            target_len = (i / count) * total_len
            # 二分查找对应位置
            lo, hi = 0, len(cum_len) - 1
            while lo < hi:
                mid = (lo + hi) // 2
                if cum_len[mid] < target_len:
                    lo = mid + 1
                else:
                    hi = mid
            # 线性插值
            if lo > 0 and cum_len[lo] - target_len > target_len - cum_len[lo - 1]:
                lo = lo - 1
            x, y = dense_points[lo]
            points.append((int(x), int(y)))

        return points

    def spawn_cat(self):
        """生成一只猫咪"""
        if self.spawn_index >= len(self.heart_points):
            return

        x, y = self.heart_points[self.spawn_index]
        gif_path = random.choice(self.gif_paths)

        cat = AnimatedCat(
            gif_path, x, y,
            CONFIG["cat_size"],
            CONFIG["black_threshold"],
            CONFIG["gif_brightness"]
        )
        self.cats.append(cat)
        self.spawn_index += 1

    def run(self):
        """主循环"""
        clock = pygame.time.Clock()
        running = True

        # 状态: spawning -> wait_after_spawn -> disappearing -> final
        state = "spawning"
        state_timer = 0
        spawn_interval = CONFIG["spawn_interval"]
        disappear_interval = CONFIG["spawn_interval"]
        total_count = len(self.heart_points)
        min_size = CONFIG["cat_size"]
        max_size = CONFIG["giant_cat_size"]
        disappear_start_time = 0
        disappear_total_time = disappear_interval * total_count  # 消失阶段总时长

        while running:
            current_time = pygame.time.get_ticks()

            # 事件处理
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False

            # === 状态机 ===

            # 阶段1: 逐个生成猫咪
            if state == "spawning":
                if current_time - self.last_spawn_time > spawn_interval:
                    if self.spawn_index < total_count:
                        self.spawn_cat()
                        self.last_spawn_time = current_time
                    else:
                        state = "wait_after_spawn"
                        state_timer = current_time

            # 阶段2: 全部生成后等待1秒
            elif state == "wait_after_spawn":
                if current_time - state_timer > 1000:
                    state = "disappearing"
                    self.disappear_index = 0
                    self.last_spawn_time = current_time
                    disappear_start_time = current_time

            # 阶段3: 按生成顺序逐个消失，同时大猫同步放大
            elif state == "disappearing":
                if current_time - self.last_spawn_time > disappear_interval:
                    if self.disappear_index < total_count:
                        self.cats.pop(0)  # 移除最早生成的
                        self.disappear_index += 1
                        self.last_spawn_time = current_time
                    else:
                        state = "final"

            # 阶段4: 大猫满尺寸，持续显示直到用户关闭
            elif state == "final":
                pass

            # === 绘制 ===
            self.screen.fill((0, 0, 0))

            # 绘制剩余爱心猫咪
            for cat in self.cats:
                cat.update(current_time)
                cat.draw(self.screen, current_time)

            # 消失过程中/最终：绘制逐渐变大的大猫
            if self.giant_frames and (state == "disappearing" or state == "final"):
                if state == "disappearing" and disappear_total_time > 0:
                    # 按时间进度连续插值，ease-out缓动
                    elapsed = current_time - disappear_start_time
                    t = min(elapsed / disappear_total_time, 1.0)
                    t = 1 - (1 - t) * (1 - t)  # ease-out quad
                    current_size = min_size + (max_size - min_size) * t
                else:
                    current_size = max_size
                self.draw_giant_cat(self.screen, current_time, current_size)

            pygame.display.flip()
            clock.tick(60)

        pygame.quit()


if __name__ == "__main__":
    app = CatHeartApp()
    app.run()
