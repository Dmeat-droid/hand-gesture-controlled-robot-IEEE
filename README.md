# 🚗🤖 Hand Gesture Controlled Car

A smart robotic car controlled using real-time hand gestures. This project combines **computer vision (Python)** and **embedded control (ESP32)** communicating over **WiFi UDP**, enabling intuitive and wireless robot movement.

---

## 📘 Overview

This system allows a user to control a robotic car using hand gestures captured from a camera. The Python program detects gestures using **MediaPipe** and **OpenCV**, then sends commands to the **ESP32** via **UDP** over WiFi. The ESP32 interprets the commands and controls the motors accordingly.

---

## ✨ Features

* Real-time hand gesture recognition
* Wireless robot control using **WiFi UDP**
* Lightweight and fast gesture detection
* ESP32-based robotic car
* Clean modular Python + Arduino/ESP32 codebase

---

## 🛠️ Technologies Used

### Python

* MediaPipe
* OpenCV
* NumPy

### Hardware

* ESP32 Development Board
* Robotic car chassis
* Motor driver
* DC motors
* WiFi network

---

## ⚙️ Installation & Setup

### 1. Clone the Repository

```
git clone https://github.com/your-username/Hand-Gesture-Controlled-Car.git
cd Hand-Gesture-Controlled-Car
```

### 2. Install Python Dependencies

Create and activate a virtual environment, then run:

```
pip install -r requirements.txt
```

### 3. Upload Code to ESP32

1. Open the `.ino` file in the Arduino folder.
2. Set board to: **ESP32 Dev Module**
3. Configure WiFi SSID and password in the Arduino code
4. Upload the program

### 4. Assemble the Car

* Connect ESP32 → Motor driver
* Connect motor driver → DC motors
* Ensure wheel rotation direction is correct

### 5. Run the Python Program

```
python main.py
```

Ensure both Python script and ESP32 are on the same **WiFi network**.

---

## 🧩 System Architecture

Camera → Python (MediaPipe + OpenCV)
→ Gesture recognized
→ Command sent via UDP
→ ESP32 receives command
→ Motor driver → Car moves

---

## 📂 Project Structure

```
project/
├── Python/
│   ├── main.py
│   ├── utils.py
│   └── requirements.txt
│
├── hand_gesture_controlled_robot/
│   └── gesture_control_car.ino
│
└── .gitignore
```

---

## 📄 License

MIT License
