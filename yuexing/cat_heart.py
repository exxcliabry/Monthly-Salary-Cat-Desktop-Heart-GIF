import tkinter as tk
from PIL import Image, ImageTk, ImageDraw
import math
import os
import random
from collections import deque

# ============================================================
#  配置参数
# ============================================================
CONFIG = {
    # 动作总数（1.gif, 2.gif, 3.gif, 4.gif, ...）
    "total_actions": 4,
    # 猫咪显示尺寸
    "cat_size": 70,
    # 爱心缩放比例
    "heart_scale": 13,
    # 轮廓上的猫咪数量
    "outline_count": 35,
    # 窗口大小
    "window_width": 700,
    "window_height": 650,
    # GIF播放速度（毫秒）
    "gif_speed": 100,
    # 抠图阈值（黑色阈值，低于此值的像素变透明）
    "black_threshold": 30,
}


def _color_dist(c1, c2):
    return math.sqrt((c1[0]-c2[0])**2 + (c1[1]-c2[1])**2 + (c1[2]-c2[2])**2)


def remove_black_bg(img, threshold=30):
    img = img.convert("RGBA")
    w, h = img.size
    pixels = img.load()

    # 1. 从四个角采样背景颜色
    corners = [(0, 0), (w-1, 0), (0, h-1), (w-1, h-1)]
    bg_r = sum(pixels[x, y][0] for x, y in corners) // 4
    bg_g = sum(pixels[x, y][1] for x, y in corners) // 4
    bg_b = sum(pixels[x, y][2] for x, y in corners) // 4
    bg_color = (bg_r, bg_g, bg_b)

    # 2. 创建二值蒙版：背景=0，前景=255
    mask = [[255] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            r, g, b = pixels[x, y][:3]
            if _color_dist((r, g, b), bg_color) < threshold * 2:
                mask[y][x] = 0

    # 3. 从四个角泛洪填充，标记与边缘相连的背景区域
    for sx, sy in corners:
        if mask[sy][sx] == 0:
            queue = deque([(sx, sy)])
            mask[sy][sx] = 128
            while queue:
                cx, cy = queue.popleft()
                for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                    nx, ny = cx+dx, cy+dy
                    if 0 <= nx < w and 0 <= ny < h and mask[ny][nx] == 0:
                        mask[ny][nx] = 128
                        queue.append((nx, ny))

    # 4. 生成带透明度的新图像，边缘做渐变混合
    result = img.copy()
    new_pixels = result.load()
    for y in range(h):
        for x in range(w):
            if mask[y][x] == 128:
                # 背景像素：检查是否靠近前景边缘（做半透明过渡）
                near_fg = False
                for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                    nx, ny = x+dx, y+dy
                    if 0 <= nx < w and 0 <= ny < h and mask[ny][nx] == 255:
                        near_fg = True
                        break
                if near_fg:
                    # 边缘像素：按颜色距离做半透明过渡
                    r, g, b = pixels[x, y][:3]
                    dist = _color_dist((r, g, b), bg_color)
                    alpha = int(max(0, min(255, (dist / threshold) * 255)))
                    new_pixels[x, y] = (r, g, b, alpha)
                else:
                    new_pixels[x, y] = (pixels[x, y][0], pixels[x, y][1], pixels[x, y][2], 0)

    return result


class AnimatedGif:

    def __init__(self, canvas, gif_path, x, y, size, threshold):
        self.canvas = canvas
        self.x = x
        self.y = y
        self.size = size
        self.threshold = threshold
        self.frames = []
        self.frame_index = 0
        self.label = None
        self.animation_id = None

        # 加载GIF所有帧
        self.load_frames(gif_path)

        if self.frames:
            # 创建标签
            self.label = tk.Label(
                canvas,
                bg="black",
                borderwidth=0,
                highlightthickness=0
            )
            self.canvas.create_window(x, y, window=self.label)
            # 开始动画
            self.animate()

    def load_frames(self, gif_path):
        try:
            img = Image.open(gif_path)
            frame_count = getattr(img, 'n_frames', 1)

            for i in range(frame_count):
                img.seek(i)
                frame = img.copy().convert("RGBA")
                frame = frame.resize((self.size, self.size), Image.Resampling.LANCZOS)
                # 抠图处理
                frame = remove_black_bg(frame, self.threshold)
                photo = ImageTk.PhotoImage(frame)
                self.frames.append(photo)

            print(f"[OK] 已加载 {gif_path}: {frame_count} 帧")
        except Exception as e:
            print(f"[FAIL] 加载失败 {gif_path}: {e}")

    def animate(self):
        if not self.frames or not self.label:
            return

        # 更新帧
        self.label.config(image=self.frames[self.frame_index])
        self.frame_index = (self.frame_index + 1) % len(self.frames)

        # 下一帧
        self.animation_id = self.canvas.after(CONFIG["gif_speed"], self.animate)

    def update_action(self, gif_path):
        # 停止当前动画
        if self.animation_id:
            self.canvas.after_cancel(self.animation_id)

        # 加载新GIF
        self.frames.clear()
        self.frame_index = 0
        self.load_frames(gif_path)

        # 重新开始动画
        if self.frames:
            self.animate()

    def destroy(self):
        if self.animation_id:
            self.canvas.after_cancel(self.animation_id)


class CatHeartApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("月薪猫爱心")

        # 获取屏幕尺寸
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        # 计算窗口位置（屏幕中心）
        x = (screen_width - CONFIG["window_width"]) // 2
        y = (screen_height - CONFIG["window_height"]) // 2
        self.root.geometry(f"{CONFIG['window_width']}x{CONFIG['window_height']}+{x}+{y}")

        # 设置透明背景（Windows）
        self.root.attributes("-transparentcolor", "black")
        self.root.attributes("-topmost", True)  # 置顶
        self.root.overrideredirect(False)  # 保留标题栏以便拖动

        # 背景色（透明部分）
        self.root.configure(bg="black")

        # 计算中心点
        self.center_x = CONFIG["window_width"] // 2
        self.center_y = CONFIG["window_height"] // 2 + 30

        # 存储动画GIF对象
        self.animated_cats = []

        # 创建UI
        self.create_widgets()

        # 生成爱心
        self.draw_heart()

    def heart_x(self, t):
        return 16 * math.pow(math.sin(t), 3)

    def heart_y(self, t):
        return -(13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t))

    def get_heart_points(self):
        points = []
        count = CONFIG["outline_count"]
        scale = CONFIG["heart_scale"]

        # 从底部开始 (t = 3π/2)，逆时针转一圈
        start_t = math.pi * 1.5

        for i in range(count):
            t = start_t - (i / count) * 2 * math.pi
            x = self.heart_x(t) * scale + self.center_x
            y = self.heart_y(t) * scale + self.center_y
            points.append((x, y))

        return points

    def create_widgets(self):
        # 标题（透明背景）
        title = tk.Label(
            self.root,
            text="🐱 月薪猫爱心 🐱",
            font=("Courier New", 20, "bold"),
            fg="#87CEEB",
            bg="black"
        )
        title.pack(pady=5)

        # 画布
        self.canvas = tk.Canvas(
            self.root,
            width=CONFIG["window_width"],
            height=CONFIG["window_height"] - 120,
            bg="black",
            highlightthickness=0
        )
        self.canvas.pack()

        # 按钮框架
        btn_frame = tk.Frame(self.root, bg="black")
        btn_frame.pack(pady=5)

        btn_style = {
            "font": ("Courier New", 11),
            "fg": "#87CEEB",
            "bg": "#1a1a2e",
            "activebackground": "#87CEEB",
            "activeforeground": "black",
            "relief": "raised",
            "bd": 2,
            "width": 12,
        }

        tk.Button(btn_frame, text="🎲 随机", command=self.randomize, **btn_style).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="✨ 统一", command=self.uniform, **btn_style).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="🔄 重绘", command=self.refresh, **btn_style).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="❌ 退出", command=self.root.quit, **btn_style).pack(side=tk.LEFT, padx=5)

        # 状态栏
        self.status_label = tk.Label(
            self.root,
            text="",
            font=("Courier New", 10),
            fg="#ADD8E6",
            bg="black"
        )
        self.status_label.pack(pady=3)

    def draw_heart(self):
        # 清除旧的
        self.canvas.delete("all")
        for cat in self.animated_cats:
            cat.destroy()
        self.animated_cats.clear()

        # 获取轮廓点
        points = self.get_heart_points()

        # 在每个点放置动态猫咪
        for i, (x, y) in enumerate(points):
            # 随机选择动作
            action = random.randint(1, CONFIG["total_actions"])
            gif_path = f"{action}.gif"

            if os.path.exists(gif_path):
                cat = AnimatedGif(
                    self.canvas, gif_path, x, y,
                    CONFIG["cat_size"], CONFIG["black_threshold"]
                )
                self.animated_cats.append(cat)

        # 更新状态
        self.update_status()

    def update_status(self):
        self.status_label.config(
            text=f"共 {len(self.animated_cats)} 只动态猫咪 | 按 R/U/F5 快捷操作"
        )

    def randomize(self):
        for cat in self.animated_cats:
            action = random.randint(1, CONFIG["total_actions"])
            gif_path = f"{action}.gif"
            if os.path.exists(gif_path):
                cat.update_action(gif_path)
        self.status_label.config(text="🎲 动作已随机！")

    def uniform(self):
        action = random.randint(1, CONFIG["total_actions"])
        gif_path = f"{action}.gif"
        if os.path.exists(gif_path):
            for cat in self.animated_cats:
                cat.update_action(gif_path)
            self.status_label.config(text=f"✨ 统一为动作 {action}")

    def refresh(self):
        self.draw_heart()
        self.status_label.config(text="🔄 爱心已重新生成！")

    def run(self):
        self.root.bind("<r>", lambda e: self.randomize())
        self.root.bind("<R>", lambda e: self.randomize())
        self.root.bind("<u>", lambda e: self.uniform())
        self.root.bind("<U>", lambda e: self.uniform())
        self.root.bind("<F5>", lambda e: self.refresh())
        self.root.bind("<Escape>", lambda e: self.root.quit())

        self.root.mainloop()


if __name__ == "__main__":
    print("启动月薪猫爱心小程序...")
    print(f"当前目录: {os.getcwd()}")
    print(f"寻找GIF文件: 1.gif ~ {CONFIG['total_actions']}.gif")
    print("-" * 40)

    app = CatHeartApp()
    app.run()
