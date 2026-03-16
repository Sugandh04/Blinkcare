import tkinter as tk
import threading
import time
import json
import os
import pystray
import winsound
from PIL import Image, ImageDraw

CONFIG_FILE = "blinkcare_config.json"

config = {
    "work_interval": 20 * 60,
    "blink_duration": 20,
    "pos_x": None,
    "pos_y": None
}

paused = False
bubble_visible = False
settings_open = False
tray_icon = None


# -----------------------------
# Config
# -----------------------------

def load_config():
    global config
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                config.update(json.load(f))
    except:
        print("Config file corrupted, using defaults")


def save_config():
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)
    except:
        pass


load_config()


# -----------------------------
# Blink Bubble
# -----------------------------

class BlinkBubble:

    def __init__(self, root):

        self.root = root
        self.window_size = 240
        self.circle_size = 120
        self.circle_offset = 60

        screen_w = root.winfo_screenwidth()
        screen_h = root.winfo_screenheight()

        self.target_x = config["pos_x"] or (screen_w - 260)
        self.target_y = config["pos_y"] or (screen_h - 260)

        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.attributes("-transparentcolor", "#000001")

        self.win.geometry(f"{self.window_size}x{self.window_size}+{screen_w}+{self.target_y}")

        self.canvas = tk.Canvas(
            self.win,
            width=self.window_size,
            height=self.window_size,
            bg="#000001",
            highlightthickness=0
        )
        self.canvas.pack()

        self.draw_card()

        x1 = self.circle_offset
        y1 = self.circle_offset
        x2 = x1 + self.circle_size
        y2 = y1 + self.circle_size

        self.bg_circle = self.canvas.create_arc(
            x1, y1, x2, y2,
            start=90,
            extent=360,
            style="arc",
            width=8,
            outline="#333"
        )

        self.circle = self.canvas.create_arc(
            x1, y1, x2, y2,
            start=90,
            extent=360,
            style="arc",
            width=8,
            outline="#00ff9f"
        )

        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2

        self.time_text = self.canvas.create_text(
            cx,
            cy,
            text="",
            fill="white",
            font=("Segoe UI", 20, "bold")
        )

        self.offset_x = 0
        self.offset_y = 0

        self.win.bind("<ButtonPress-1>", self.start_move)
        self.win.bind("<B1-Motion>", self.move)

        self.win.withdraw()

    # UI card
    def draw_card(self):

        r = 25
        x1, y1 = 10, 10
        x2, y2 = self.window_size - 10, self.window_size - 10

        points = [
            x1+r,y1,x2-r,y1,x2,y1,x2,y1+r,
            x2,y2-r,x2,y2,x2-r,y2,x1+r,y2,
            x1,y2,x1,y2-r,x1,y1+r,x1,y1
        ]

        self.canvas.create_polygon(points, smooth=True, fill="#1e1e1e")

        self.canvas.create_text(
            self.window_size/2,
            35,
            text="Blink Your Eyes",
            fill="white",
            font=("Segoe UI",12,"bold")
        )

    # dragging
    def start_move(self,event):
        self.offset_x=event.x
        self.offset_y=event.y

    def move(self,event):

        x=self.win.winfo_x()+event.x-self.offset_x
        y=self.win.winfo_y()+event.y-self.offset_y

        self.win.geometry(f"+{x}+{y}")

        config["pos_x"]=x
        config["pos_y"]=y
        save_config()

        self.target_x=x
        self.target_y=y

    # animation
    def slide_in(self):

        x=self.win.winfo_x()

        if x>self.target_x:

            step=max(1,(x-self.target_x)//6)

            x-=step

            self.win.geometry(f"+{x}+{self.target_y}")

            self.root.after(10,self.slide_in)

    # show bubble
    def show(self):

        global bubble_visible,tray_icon

        if bubble_visible:
            return

        bubble_visible=True

        if tray_icon:
            tray_icon.title="BlinkCare\nBlink time"

        screen_w=self.root.winfo_screenwidth()

        self.win.geometry(f"+{screen_w}+{self.target_y}")

        self.win.deiconify()

        self.slide_in()

        self.start_time=time.time()
        self.duration=config["blink_duration"]

        self.animate()

    # timer
    def animate(self):

        global paused

        if paused:
            self.root.after(100,self.animate)
            return

        elapsed=time.time()-self.start_time
        remaining=max(0,self.duration-elapsed)

        progress=(remaining/self.duration)*360

        self.canvas.itemconfig(self.circle,extent=progress)
        self.canvas.itemconfig(self.time_text,text=str(int(remaining)))

        if remaining>0:
            self.root.after(30,self.animate)
        else:
            winsound.PlaySound("SystemAsterisk",winsound.SND_ALIAS)
            self.close()

    def close(self):

        global bubble_visible

        bubble_visible=False
        self.win.withdraw()


# -----------------------------
# Cycle Controller
# -----------------------------

def cycle_loop(root,bubble):

    global paused,tray_icon

    while root.winfo_exists():

        while paused:
            time.sleep(1)

        root.after(0,bubble.show)

        while bubble_visible:
            time.sleep(0.5)

        start=time.time()

        while True:

            if paused:
                break

            elapsed=time.time()-start
            remaining=config["work_interval"]-elapsed

            if tray_icon and remaining>0:
                m=int(remaining//60)
                s=int(remaining%60)
                tray_icon.title=f"BlinkCare\nNext blink in {m:02}:{s:02}"

            if elapsed>=config["work_interval"]:
                break

            time.sleep(1)


# -----------------------------
# Settings
# -----------------------------

def open_settings():

    global settings_open

    if settings_open:
        return

    settings_open=True

    win=tk.Toplevel()
    win.title("BlinkCare Settings")

    tk.Label(win,text="Work interval (minutes)").pack()

    interval=tk.Entry(win)
    interval.insert(0,config["work_interval"]//60)
    interval.pack()

    tk.Label(win,text="Blink duration (seconds)").pack()

    duration=tk.Entry(win)
    duration.insert(0,config["blink_duration"])
    duration.pack()

    def save():

        try:
            config["work_interval"]=int(interval.get())*60
            config["blink_duration"]=int(duration.get())
            save_config()
        except:
            pass

        close()

    def close():
        global settings_open
        settings_open=False
        win.destroy()

    tk.Button(win,text="Save",command=save).pack(pady=10)

    win.protocol("WM_DELETE_WINDOW",close)


# -----------------------------
# Tray
# -----------------------------

def create_icon():

    img=Image.new("RGB",(64,64),(30,30,30))
    d=ImageDraw.Draw(img)
    d.ellipse((16,16,48,48),fill="white")

    return img


def tray_pause(icon,item):
    global paused
    paused=True


def tray_resume(icon,item):
    global paused
    paused=False


def tray_settings(icon,item):
    root.after(0,open_settings)


def tray_exit(icon,item):
    icon.stop()
    root.after(0,root.quit)


def setup_tray():

    global tray_icon

    tray_icon=pystray.Icon(
        "BlinkCare",
        create_icon(),
        "BlinkCare",
        menu=pystray.Menu(
            pystray.MenuItem("Pause",tray_pause),
            pystray.MenuItem("Resume",tray_resume),
            pystray.MenuItem("Settings",tray_settings),
            pystray.MenuItem("Exit",tray_exit)
        )
    )

    tray_icon.run()


# -----------------------------
# Startup
# -----------------------------

def add_to_startup():

    startup=os.path.join(
        os.getenv("APPDATA"),
        r"Microsoft\Windows\Start Menu\Programs\Startup"
    )

    script=os.path.abspath(__file__)
    bat=os.path.join(startup,"BlinkCare.bat")

    if not os.path.exists(bat):

        with open(bat,"w") as f:
            f.write(f'python "{script}"')


# -----------------------------
# Main
# -----------------------------

root=tk.Tk()
root.withdraw()

bubble=BlinkBubble(root)

add_to_startup()

threading.Thread(
    target=cycle_loop,
    args=(root,bubble),
    daemon=True
).start()

threading.Thread(
    target=setup_tray,
    daemon=True
).start()

root.mainloop()