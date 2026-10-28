# Target Detection and Alarm System (YOLOv8 + ESP32-CAM)

A low-cost surveillance project that looks for **one chosen object** in live video. You give a photo of the target, pick a camera, and the system raises an alarm when it sees that object. It also estimates the **distance, height and width** of the target.

The video can come from an **ESP32-CAM**, a **phone camera** or a **PC webcam**. The alarm can be **virtual** (PC sound and an on-screen red LED) or **real** (an ESP32 buzzer and a real red LED). **No Arduino Uno is needed.**

---

## Features

- Three video sources, chosen from a menu: ESP32-CAM, phone, PC webcam.
- The target is set by a photo placed in the `target/` folder.
- Uses a pre-trained **YOLOv8** model, so no training is needed.
- Two-step matching: object class (YOLO) and colour appearance (HSV histogram).
- On detection: red box, **WARNING** banner on the PC, buzzer and red LED.
- Choice of alarm type: virtual (PC) or real (ESP32 hardware).
- Distance, height and width estimate from a single camera, with one-key calibration.
- Live tuning of the colour match while the program runs.
- Runs on Windows, macOS and Linux (Python 3.9 to 3.12).

---

## How it works

```
Camera (ESP32-CAM / Phone / PC)
            |  live video
            v
   PC: Python + OpenCV + YOLOv8
            |
   find objects in each frame
            |
   same class as target photo?  AND  colour similar?
            |  yes
            v
   WARNING on PC + buzzer + red LED + distance / size
   (virtual on the PC, or real through the ESP32)
```

The ESP32 only streams video and switches the buzzer and LED. All the heavy image processing runs on the PC.

---

## Project structure

```
target_detection_project/
|-- main.py                     PC program (run this)
|-- requirements.txt
|-- README.md
|-- target/                     put your target photo(s) here
|   `-- bottle.jpg
`-- esp32_cam_alarm/
    `-- esp32_cam_alarm.ino     ESP32-CAM firmware
```

---

## Hardware

You only need the PC for the **virtual** alarm. The parts below are for the ESP32 camera and the **real** alarm.

| Part | Quantity | Note |
|---|---|---|
| ESP32-CAM (AI-Thinker) + USB base board (ESP32-CAM-MB) or FTDI programmer | 1 | Required for option 1 and for the real alarm |
| Red LED | 1 | Real warning light |
| Active buzzer (5 V) | 1 | Real sound alarm |
| Resistor 220 ohm | 1 | **Optional**. Recommended in series with a bare LED. Not needed for an LED module with a built-in resistor |
| Resistor 1 kohm + transistor 2N2222 | 1 each | **Optional**. Only if the buzzer is weak and needs a transistor |
| Jumper wires, breadboard | as needed | |
| 5 V, 1 A power supply | 1 | A weak supply gives a black picture or restarts |

### Wiring

| ESP32-CAM pin | Connected to |
|---|---|
| GPIO14 | Red LED anode (through the optional 220 ohm resistor) |
| GPIO13 | Active buzzer positive |
| GND | LED cathode and buzzer negative |
| 5V | 5 V supply |

---

## Installation

### 1. PC (needed for everything)

1. Install **Python 3.9 to 3.12** and tick **Add Python to PATH**.
2. Download or clone this repository.
3. Open a terminal in the project folder and run:

   ```bash
   pip install -r requirements.txt
   ```

   (or `pip install ultralytics opencv-python numpy requests`)
4. Put your target photo in the `target/` folder.

The model `yolov8n.pt` downloads automatically on the first run, so keep the internet on.

### 2. ESP32-CAM firmware (option 1 or real alarm)

1. Install **Arduino IDE 2.x**.
2. Open *File > Preferences* and add this to *Additional Boards Manager URLs*:
   `https://espressif.github.io/arduino-esp32/package_esp32_index.json`
3. Open *Tools > Board > Boards Manager*, search `esp32` and install **esp32 by Espressif**.
4. Select the board **AI Thinker ESP32-CAM** and the partition scheme **Huge APP**.
5. Open `esp32_cam_alarm/esp32_cam_alarm.ino`, write your WiFi name and password, then upload.
   With an FTDI adapter, connect GPIO0 to GND while uploading, then remove it and press reset.
6. Open the Serial Monitor at **115200 baud** and press reset. It prints the IP address, for example `192.168.1.50`.
7. Test in a browser:
   - Video: `http://192.168.1.50:81/stream`
   - Buzzer and LED on: `http://192.168.1.50/alarm?state=1`
   - Buzzer and LED off: `http://192.168.1.50/alarm?state=0`

Close the browser tab with the video before running `main.py`. The ESP32 serves one viewer at a time. The ESP32 and the PC must be on the same **2.4 GHz** WiFi network.

> If you get a compile error for `pin_sscb_sda` and `pin_sscb_scl`, rename them to `pin_sccb_sda` and `pin_sccb_scl`. This depends on the ESP32 board package version.

### 3. Phone camera (option 2)

Choose one method:

- **DroidCam or Iriun Webcam (easiest).** Install the phone app and its PC client, connect by USB or WiFi, and check that the PC client shows the phone video. The phone then works like a webcam with a camera number.
- **IP Webcam (Android).** Install the app, tap *Start server* and open the address shown in the PC browser to check it. Use the URL `http://PHONE_IP:8080/video` in the program.

---

## Usage

```bash
python main.py
```

1. Choose the video source:

   ```
   1) ESP32-CAM
   2) Phone camera
   3) PC webcam
   ```
2. Enter the ESP32 IP, the phone camera number/URL, or the webcam number (the program lists the working camera numbers for you).
3. Choose the alarm type:

   ```
   1) VIRTUAL - sound from PC speaker + red circle on screen
   2) REAL    - ESP32 buzzer + real red LED (needs ESP32)
   ```
4. YOLO reads your target photo and shows what it recognised. Enter the real height of the object in cm (or press Enter for a default).
5. Show the target to the camera. You will see a red box, the WARNING banner, the alarm, and the distance and size.

**PC only, no hardware:** choose option 3, then the virtual alarm.

### Keys in the video window

| Key | Action |
|---|---|
| `q` | Quit |
| `c` | Calibrate distance (type the true distance of the target in cm) |
| `m` | Switch the colour check on or off (class-only mode) |
| `+` / `-` | Raise or lower the colour threshold |

---

## How YOLO recognises your target photo

1. YOLOv8 runs on the photo in `target/` and finds all known objects.
2. The **largest object** becomes the target. Its class (for example `bottle`) is the target class.
3. The program saves the object's **colour fingerprint** (HSV histogram).
4. In live video, YOLO finds all objects. The program keeps only objects of the **same class** and compares their colour with your photo.
5. If both match, the alarm starts. It stays on for 2 seconds after the target disappears, so it does not flicker.

The pre-trained model knows only the **80 COCO classes** (person, bottle, cup, cell phone, laptop, book, chair, backpack, dog, cat and so on). A photo of something outside these classes is rejected with a message.

**Tips for a good target photo:** one main object, large and centred, good light, plain background. For best colour match, take the photo with the same camera you will use for detection.

---
## Image

<img width="764" height="417" alt="image" src="https://github.com/user-attachments/assets/55e75d27-51f1-42a2-b04f-8ac55e3b6040" />



## Distance and size estimate

The program uses the pinhole camera model:

```
distance = real_height x focal_length_px / height_in_pixels
```

- The real height comes from your input (or an average value for that class).
- The focal length starts from the camera field of view. For better accuracy, put the target at a known distance, press `c` and type the distance.
- Accuracy depends on the real height you enter and on how well the box fits the object. It is an estimate, not a measurement.

---

## Settings

Edit these values at the top of `main.py`:

| Setting | Default | Meaning |
|---|---|---|
| `MODEL_NAME` | `yolov8n.pt` | Use `yolov8s.pt` for higher accuracy (slower) |
| `CONF` | `0.25` | YOLO confidence. Lower detects more objects |
| `HIST_THRESH` | `0.30` | Colour match from 0 to 1. Higher is stricter |
| `HOLD_SEC` | `2.0` | Seconds the alarm stays on after the last sighting |
| `FOV_DEG` | `65 / 65 / 60` | Approximate field of view for ESP32 / phone / PC |
| `REAL_H` | table | Average real height (cm) of common objects |

---

## Live window while searching for the target

<img width="760" height="616" alt="image" src="https://github.com/user-attachments/assets/17d554d6-48d1-4875-b858-d1f6833764f8" />


## Live window after the target is detected: red box, WARNING banner, virtual LED, distance and width

<img width="748" height="603" alt="image" src="https://github.com/user-attachments/assets/c6af5109-9cc1-4b0f-afbc-ce42795bbae8" />



## Troubleshooting

| Problem | Likely cause | Fix |
|---|---|---|
| The box shows the right name but no warning | The colour check rejects it (grey or orange box) | Press `m` for class-only mode, or press `-` to lower the threshold. Use a target photo taken with the same camera |
| No box around the object | YOLO does not detect it (small, dark, blurry, far) | Move closer, add light, hold still |
| Wrong class name (for example `cell phone`) | The target is shown as a photo on a screen | Show the real object |
| Phone: cannot open camera | PC cannot reach the phone | Open the phone URL in the PC browser first. Use the same WiFi, no VPN, no guest network. Or use DroidCam / Iriun |
| ESP32 Serial Monitor shows only dots | Wrong WiFi data or a 5 GHz network | Check name/password and use 2.4 GHz |
| ESP32 video is black or restarts | Weak power supply | Use a 5 V, 1 A supply and a good cable |
| ESP32 stream works only once | One viewer at a time | Close other tabs that show the stream |
| No beep on the PC | Volume is muted | Unmute. The beep is best on Windows; macOS and Linux play a system sound |
| PC webcam does not open | Another app uses it, or wrong number | Close Zoom/Teams and try another camera number |

To list working cameras:

```bash
python -c "import cv2; [print(i, cv2.VideoCapture(i).isOpened()) for i in range(5)]"
```

---

## Limitations

- Only the 80 COCO classes can be a target.
- Matching uses class and colour only. Two similar objects of the same class can both match.
- The ESP32-CAM colours can differ from other cameras, so the colour score may be lower.
- Distance is an estimate and needs the correct real height.
- ESP32 and phone options need a stable WiFi link.

## Future work

- Custom-trained YOLO model for any object.
- Better matching with learned image embeddings.
- Object tracking and a depth sensor for distance.
- Phone or e-mail alerts (MQTT, messaging apps).
- Several targets at once and a standalone ESP32 version.

---

## Tech stack

Python, OpenCV, Ultralytics YOLOv8, requests, Arduino framework for ESP32.

## Authors

- Aditya Vikram Singh
- Aditya Tripathy
