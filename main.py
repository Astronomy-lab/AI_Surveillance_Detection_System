"""
TARGET DETECTION SYSTEM  (YOLOv8 pre-trained)
Source  : 1) ESP32-CAM   2) Phone   3) PC webcam
Output  : PC warning + red virtual LED + beep, ESP32 buzzer + real red LED (optional),
          distance / height / width estimate.
No Arduino Uno needed.
"""
import os, sys, time, math, threading, platform

try:
    import cv2
    from ultralytics import YOLO
except ImportError:
    sys.exit("Missing packages. Run:  pip install ultralytics opencv-python numpy requests")

try:
    import requests
except ImportError:
    requests = None

# ===================== SETTINGS =====================
TARGET_DIR  = "target"
MODEL_NAME  = "yolov8n.pt"   # yolov8s.pt = more accurate but slower
CONF        = 0.35           # YOLO confidence for live video
HIST_THRESH = 0.45           # colour/appearance match 0..1 (higher = stricter)
HOLD_SEC    = 2.0            # alarm stays on this long after target last seen
FOV_DEG     = {1: 65, 2: 65, 3: 60}   # approx horizontal field of view per source

REAL_H = {   # average real height in cm (used for distance). You can overwrite at start.
    "person": 170, "bottle": 25, "cup": 10, "cell phone": 15, "laptop": 24,
    "book": 22, "chair": 90, "backpack": 45, "umbrella": 100, "tv": 50,
    "mouse": 4, "keyboard": 3, "apple": 8, "banana": 20, "orange": 8,
    "clock": 25, "vase": 25, "scissors": 17, "handbag": 30, "suitcase": 60,
    "bicycle": 100, "car": 150, "dog": 50, "cat": 25,
}
# ====================================================

alarm_on = False


# ---------- threaded camera: always newest frame, low lag ----------
class Cam:
    def __init__(self, src):
        if isinstance(src, int) and platform.system() == "Windows":
            self.cap = cv2.VideoCapture(src, cv2.CAP_DSHOW)
        else:
            self.cap = cv2.VideoCapture(src)
        self.ok = self.cap.isOpened()
        self.frame = None
        self.running = True
        if self.ok:
            threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while self.running:
            r, f = self.cap.read()
            if r:
                self.frame = f
            else:
                time.sleep(0.05)

    def read(self):
        return None if self.frame is None else self.frame.copy()

    def stop(self):
        self.running = False
        time.sleep(0.1)
        self.cap.release()


def scan_cameras(n=6):
    found = []
    for i in range(n):
        c = cv2.VideoCapture(i, cv2.CAP_DSHOW) if platform.system() == "Windows" \
            else cv2.VideoCapture(i)
        if c.isOpened():
            found.append(i)
        c.release()
    return found


# ---------- alarm: VIRTUAL (PC sound) or REAL (ESP32 buzzer + LED) ----------
def pc_beep():
    sysname = platform.system()
    if sysname == "Windows":
        import winsound
        winsound.Beep(2000, 300)
    elif sysname == "Darwin":
        os.system("afplay /System/Library/Sounds/Funk.aiff >/dev/null 2>&1")
    else:
        if os.system("paplay /usr/share/sounds/freedesktop/stereo/bell.oga >/dev/null 2>&1") != 0:
            print("\a", end="", flush=True)
            time.sleep(0.4)


class Alarm:
    def __init__(self, kind, esp_ip=""):
        self.kind = kind          # "virtual" or "real"
        self.ip = esp_ip
        self.state = False
        if kind == "virtual":
            threading.Thread(target=self._beep_loop, daemon=True).start()

    def set(self, on):
        global alarm_on
        alarm_on = on
        if on == self.state:
            return
        self.state = on
        if self.kind == "real":
            threading.Thread(target=self._send, args=(on,), daemon=True).start()

    def _send(self, on):
        try:
            requests.get(f"http://{self.ip}/alarm?state={int(on)}", timeout=2)
        except Exception:
            print("[!] ESP32 alarm not reachable (check IP / same WiFi)")

    def _beep_loop(self):
        while True:
            if alarm_on:
                pc_beep()
            else:
                time.sleep(0.05)


def test_esp32(ip):
    if requests is None:
        return False
    try:
        requests.get(f"http://{ip}/alarm?state=0", timeout=3)
        return True
    except Exception:
        return False


# ---------- target image handling ----------
def appearance_hist(img):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    h = cv2.calcHist([hsv], [0, 1], None, [30, 32], [0, 180, 0, 256])
    cv2.normalize(h, h, 0, 1, cv2.NORM_MINMAX)
    return h


def load_target(model):
    os.makedirs(TARGET_DIR, exist_ok=True)
    files = [f for f in os.listdir(TARGET_DIR)
             if f.lower().endswith((".jpg", ".jpeg", ".png", ".bmp", ".webp"))]
    if not files:
        sys.exit(f"[!] Put a target photo inside the '{TARGET_DIR}' folder and run again.")
    if len(files) == 1:
        f = files[0]
    else:
        print("\nTarget images:")
        for i, name in enumerate(files, 1):
            print(f"  {i}) {name}")
        k = input(f"Choose target [1-{len(files)}] (Enter = 1): ").strip()
        f = files[int(k) - 1] if k.isdigit() and 1 <= int(k) <= len(files) else files[0]

    img = cv2.imread(os.path.join(TARGET_DIR, f))
    if img is None:
        sys.exit(f"[!] Cannot read image {f}")
    res = model(img, conf=0.25, verbose=False)[0]
    if len(res.boxes) == 0:
        sys.exit("[!] YOLO found no known object in the target photo.\n"
                 "    Use a clear photo, object big and centred. (YOLO knows 80 COCO classes.)")

    # biggest detected object = the target
    best, best_area = None, 0
    for b in res.boxes:
        x1, y1, x2, y2 = map(int, b.xyxy[0])
        area = (x2 - x1) * (y2 - y1)
        if area > best_area:
            best, best_area = (int(b.cls[0]), x1, y1, x2, y2, float(b.conf[0])), area
    cid, x1, y1, x2, y2, cf = best
    name = model.names[cid]
    print(f"\n[YOLO] '{f}' recognised as: '{name}' ({cf:.0%})")
    print("       All objects YOLO saw in this photo:",
          ", ".join(f"{model.names[int(b.cls[0])]} {float(b.conf[0]):.0%}" for b in res.boxes))

    # show how YOLO recognised the photo
    shown = res.plot()
    cv2.rectangle(shown, (x1, y1), (x2, y2), (0, 0, 255), 3)
    cv2.putText(shown, f"TARGET = {name}", (x1, max(20, y1 - 10)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
    h0, w0 = shown.shape[:2]
    if max(h0, w0) > 800:
        s = 800 / max(h0, w0)
        shown = cv2.resize(shown, (int(w0 * s), int(h0 * s)))
    cv2.imshow("How YOLO recognised your target photo (auto-closes in 4 s)", shown)
    cv2.waitKey(4000)
    cv2.destroyAllWindows()

    crop = img[max(0, y1):y2, max(0, x1):x2]
    return cid, name, appearance_hist(crop)


# ---------- source selection ----------
def ask_int(prompt, valid=None, default=None):
    while True:
        s = input(prompt).strip()
        if not s and default is not None:
            return default
        if s.lstrip("-").isdigit():
            v = int(s)
            if valid is None or v in valid:
                return v
        print("  Invalid input, try again.")


def fix_url(u):
    u = u.strip()
    if not u.startswith("http"):
        u = "http://" + u
    rest = u.split("://", 1)[1]
    if "/" not in rest:          # only host:port typed -> add /video
        u += "/video"
    return u


def choose_alarm(default_real=False):
    print("\nBuzzer + LED type:")
    print("  1) VIRTUAL - sound from PC speaker + red circle on screen")
    print("  2) REAL    - ESP32 buzzer + real red LED (needs ESP32)")
    d = 2 if default_real else 1
    k = ask_int(f"Choose [1/2] (Enter = {d}): ", valid=(1, 2), default=d)
    return "real" if k == 2 else "virtual"


def choose_source():
    print("=" * 44)
    print("   TARGET DETECTION SYSTEM")
    print("=" * 44)
    print(" 1) ESP32-CAM")
    print(" 2) Phone camera")
    print(" 3) PC webcam")
    mode = ask_int("Select source [1/2/3]: ", valid=(1, 2, 3))
    esp_ip = ""

    if mode == 1:
        esp_ip = input("ESP32-CAM IP (e.g. 192.168.1.50): ").strip()
        src = f"http://{esp_ip}:81/stream"

    elif mode == 2:
        print("\nHow is the phone connected?")
        print("  a) DroidCam / Iriun Webcam (phone = camera number)   <- easiest")
        print("  b) IP Webcam app (URL like http://192.168.1.60:8080/video)")
        m = input("Choose [a/b] (Enter = a): ").strip().lower() or "a"
        if m == "b":
            src = fix_url(input("Phone URL: "))
            print("Using:", src)
        else:
            print("\nScanning cameras (start DroidCam/Iriun on phone + PC first) ...")
            cams = scan_cameras()
            print("Working camera numbers:", cams if cams else "none found")
            d = 1 if 1 in cams else (cams[-1] if cams else 1)
            src = ask_int(f"Phone camera number (Enter = {d}): ", default=d)

    else:
        print("\nScanning cameras ...")
        cams = scan_cameras()
        print("Working camera numbers:", cams if cams else "none found")
        src = ask_int("PC webcam number (Enter = 0): ", default=0)

    # ---- buzzer / LED type ----
    kind = choose_alarm(default_real=(mode == 1))
    if kind == "real":
        if not esp_ip:
            esp_ip = input("ESP32 IP for buzzer/LED (e.g. 192.168.1.50): ").strip()
        print("Checking ESP32 ...", end=" ")
        if test_esp32(esp_ip):
            print("connected OK")
        else:
            print("NOT reachable.")
            if input("Use VIRTUAL alarm instead? [Y/n]: ").strip().lower() != "n":
                kind = "virtual"
    return mode, src, kind, esp_ip


# ---------- main ----------
def main():
    mode, src, kind, esp_ip = choose_source()

    print("\nLoading YOLO ... (first run downloads the model)")
    model = YOLO(MODEL_NAME)
    t_cls, t_name, t_hist = load_target(model)

    default_h = REAL_H.get(t_name, 30)
    s = input(f"Real height of your '{t_name}' in cm (Enter = {default_h}): ").strip()
    try:
        real_h = float(s) if s else float(default_h)
    except ValueError:
        real_h = float(default_h)

    cam = Cam(src)
    if not cam.ok:
        sys.exit("[!] Cannot open camera.\n"
                 "    ESP32: check IP and open http://IP:81/stream in a browser.\n"
                 "    Phone: make sure DroidCam/Iriun is connected, or the URL opens in the PC browser.\n"
                 "    PC   : try another camera number, close Zoom/Teams.")
    alarm = Alarm(kind, esp_ip)

    focal, last_seen, last_hpx = None, 0, None
    print("\nRunning.  Keys in video window:  q = quit   c = calibrate distance\n")

    while True:
        frame = cam.read()
        if frame is None:
            time.sleep(0.02)
            continue
        H, W = frame.shape[:2]
        if focal is None:
            focal = (W / 2) / math.tan(math.radians(FOV_DEG[mode]) / 2)

        res = model(frame, conf=CONF, verbose=False)[0]
        target_box, best_score = None, 0

        for b in res.boxes:
            x1, y1, x2, y2 = map(int, b.xyxy[0])
            cid = int(b.cls[0])
            if cid == t_cls:
                crop = frame[max(0, y1):y2, max(0, x1):x2]
                if crop.size:
                    sc = cv2.compareHist(t_hist, appearance_hist(crop), cv2.HISTCMP_CORREL)
                    if sc >= HIST_THRESH and sc > best_score:
                        best_score, target_box = sc, (x1, y1, x2, y2)
                        continue
            cv2.rectangle(frame, (x1, y1), (x2, y2), (150, 150, 150), 1)
            cv2.putText(frame, model.names[cid], (x1, max(12, y1 - 4)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (150, 150, 150), 1)

        now = time.time()
        if target_box:
            last_seen = now
            x1, y1, x2, y2 = target_box
            hpx, wpx = max(1, y2 - y1), x2 - x1
            last_hpx = hpx
            dist = real_h * focal / hpx          # cm
            width = wpx * dist / focal           # cm
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 3)
            cv2.putText(frame, f"TARGET {t_name} {best_score:.2f}", (x1, max(15, y1 - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            for i, t in enumerate([f"Distance: {dist/100:.2f} m",
                                   f"Height  : {real_h:.0f} cm (ref)",
                                   f"Width   : {width:.0f} cm (est)"]):
                cv2.putText(frame, t, (x1, min(H - 5, y2 + 20 + 20 * i)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 2)

        active = (now - last_seen) < HOLD_SEC
        alarm.set(active)
        if active:
            cv2.rectangle(frame, (0, 0), (W, 45), (0, 0, 255), -1)
            cv2.putText(frame, "WARNING!  TARGET DETECTED  (" + ("ESP32 BUZZER + LED" if kind == "real" else "VIRTUAL BUZZER + LED") + ")", (10, 31),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
            cv2.circle(frame, (W - 25, 70), 14, (0, 0, 255), -1)       # virtual red LED ON
        else:
            cv2.putText(frame, f"Searching for: {t_name}", (10, 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.circle(frame, (W - 25, 25), 14, (60, 60, 60), -1)      # LED OFF

        cv2.imshow("Target Detection", frame)
        k = cv2.waitKey(1) & 0xFF
        if k == ord("q"):
            break
        if k == ord("c") and last_hpx:
            d = input("Calibration: target is how many cm from the camera? ").strip()
            try:
                focal = last_hpx * float(d) / real_h
                print(f"[OK] focal length = {focal:.1f} px")
            except ValueError:
                print("[!] not a number, skipped")

    alarm.set(False)
    time.sleep(0.3)
    cam.stop()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
