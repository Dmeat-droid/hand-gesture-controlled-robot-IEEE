import cv2
import mediapipe as mp
import socket
import math
import numpy as np
import time
from collections import deque

# Konfigurasi UDP untuk ESP32
UDP_IP = "192.168.1.8"  # Ganti dengan IP ESP32 Anda
UDP_PORT = 4210
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Inisialisasi MediaPipe Hands
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(static_image_mode=False,
                     max_num_hands=1,
                     min_detection_confidence=0.6,
                     min_tracking_confidence=0.6)
mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles

# Parameter kontrol
MIN_SPEED = 80
MAX_SPEED = 255
DEADZONE = 20  # Zona mati untuk mencegah drift kecil

# Smoothing untuk kontrol
motorA_history = deque(maxlen=3)
motorB_history = deque(maxlen=3)

# Parameter untuk menghindari flicker
last_command = None
last_command_time = 0
command_cooldown = 0.05

cap = cv2.VideoCapture(0)

def calculate_palm_center(landmarks):
    """Hitung pusat telapak tangan"""
    x_sum = landmarks[0].x + landmarks[5].x + landmarks[9].x + landmarks[13].x + landmarks[17].x
    y_sum = landmarks[0].y + landmarks[5].y + landmarks[9].y + landmarks[13].y + landmarks[17].y
    return (x_sum / 5, y_sum / 5)

def map_value(value, in_min, in_max, out_min, out_max):
    """Pemetaan nilai dari satu rentang ke rentang lain"""
    return (value - in_min) * (out_max - out_min) / (in_max - in_min) + out_min

def send_motor_values(motorA, motorB):
    """Kirim nilai motor langsung ke ESP32"""
    global last_command, last_command_time
    current_time = time.time()
    
    command = f"{motorA},{motorB}"
    
    # Hanya kirim jika berbeda dari perintah terakhir atau cooldown sudah berlalu
    if last_command != command or (current_time - last_command_time) > command_cooldown:
        sock.sendto(command.encode(), (UDP_IP, UDP_PORT))
        print(f"Sent: MotorA={motorA}, MotorB={motorB}")
        last_command = command
        last_command_time = current_time

def smooth_value(value, history):
    """Smoothing nilai menggunakan rata-rata"""
    history.append(value)
    return sum(history) / len(history)

def is_hand_closed(landmarks):
    """Cek apakah tangan tertutup dengan metode yang lebih sederhana"""
    # Metode 1: Cek apakah ujung jari lebih rendah dari MCP joints
    finger_tips = [8, 12, 16, 20]  # INDEX_TIP, MIDDLE_TIP, RING_TIP, PINKY_TIP
    finger_pips = [6, 10, 14, 18]  # PIP joints (sendi tengah jari)
    
    closed_fingers = 0
    for tip, pip in zip(finger_tips, finger_pips):
        if landmarks[tip].y > landmarks[pip].y:  # Ujung jari lebih rendah dari sendi tengah
            closed_fingers += 1
    
    # Cek ibu jari secara terpisah (berbeda orientasi)
    thumb_tip = landmarks[4]
    thumb_ip = landmarks[3]
    thumb_closed = abs(thumb_tip.x - landmarks[0].x) < abs(thumb_ip.x - landmarks[0].x)
    
    if thumb_closed:
        closed_fingers += 1
    
    # Tangan dianggap tertutup jika 4 atau lebih jari tertutup
    return closed_fingers >= 4

def calculate_motor_values(palm_x, palm_y, angle, hand_closed):
    """Hitung nilai motor berdasarkan posisi dan sudut tangan"""
    
    # Base speed berdasarkan posisi Y tangan (tinggi tangan)
    normalized_y = max(0, min(1, (0.8 - palm_y) / 0.6))  # Tangan atas = cepat
    base_speed = int(map_value(normalized_y, 0, 1, MIN_SPEED, MAX_SPEED))
    
    # Pastikan ada speed minimum saat tangan dikepal
    if hand_closed and base_speed < 100:
        base_speed = 100  # Speed minimum untuk mundur
    
    # Steering berdasarkan sudut
    steering_factor = max(-1, min(1, angle / 45.0))  # -1 = kiri penuh, 1 = kanan penuh
    
    # Hitung nilai motor individual
    if abs(steering_factor) < 0.1:  # Deadzone untuk jalan lurus
        motorA_speed = base_speed
        motorB_speed = base_speed
    else:
        # Differential steering
        turn_intensity = abs(steering_factor)
        speed_diff = int(abs(base_speed) * turn_intensity * 0.6)  # Gunakan abs() untuk menghindari masalah negatif
        
        if steering_factor < 0:  # Belok kiri
            motorA_speed = base_speed - speed_diff  # Motor kiri lebih lambat
            motorB_speed = base_speed + speed_diff//2  # Motor kanan lebih cepat
        else:  # Belok kanan
            motorA_speed = base_speed + speed_diff//2  # Motor kiri lebih cepat
            motorB_speed = base_speed - speed_diff  # Motor kanan lebih lambat
    
    # Jika tangan dikepal, ubah ke mode mundur (buat negatif)
    if hand_closed:
        motorA_speed = -abs(motorA_speed)  # Paksa negatif untuk mundur
        motorB_speed = -abs(motorB_speed)  # Paksa negatif untuk mundur
    
    # Batasi nilai motor
    motorA_speed = max(-255, min(255, motorA_speed))
    motorB_speed = max(-255, min(255, motorB_speed))
    
    # Apply deadzone untuk mencegah nilai kecil
    if abs(motorA_speed) < DEADZONE:
        motorA_speed = 0
    if abs(motorB_speed) < DEADZONE:
        motorB_speed = 0
        
    return int(motorA_speed), int(motorB_speed)

def draw_control_indicators(image, motorA, motorB, angle, hand_closed):
    """Gambar indikator kontrol di layar"""
    h, w, _ = image.shape
    
    # Motor A indicator (kanan) - gunakan warna berbeda untuk mundur
    motorA_height = int((abs(motorA) / MAX_SPEED) * h * 0.6)
    motorA_color = (0, 0, 255) if motorA < 0 else (0, 255, 0)  # Merah untuk mundur, hijau untuk maju
    cv2.rectangle(image, (30, h - 50), (60, h - 50 - motorA_height), motorA_color, -1)
    cv2.rectangle(image, (30, h - 50), (60, h - 50 - int(0.6 * h)), (255, 255, 255), 2)
    cv2.putText(image, "RA", (30, h - 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    
    # Motor B indicator (kiri) - gunakan warna berbeda untuk mundur
    motorB_height = int((abs(motorB) / MAX_SPEED) * h * 0.6)
    motorB_color = (0, 0, 255) if motorB < 0 else (0, 255, 0)  # Merah untuk mundur, hijau untuk maju
    cv2.rectangle(image, (w - 60, h - 50), (w - 30, h - 50 - motorB_height), motorB_color, -1)
    cv2.rectangle(image, (w - 60, h - 50), (w - 30, h - 50 - int(0.6 * h)), (255, 255, 255), 2)
    cv2.putText(image, "LB", (w - 60, h - 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    
    # Status text
    status = "MUNDUR" if hand_closed else "MAJU"
    cv2.putText(image, f"Status: {status}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
    cv2.putText(image, f"Motor A: {motorA}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
    cv2.putText(image, f"Motor B: {motorB}", (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
    cv2.putText(image, f"Sudut: {angle:.1f}°", (10, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
    cv2.putText(image, f"Kepal: {'Ya' if hand_closed else 'Tidak'}", (10, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 255) if hand_closed else (0, 255, 255), 2)
    
    # Steering indicator (horizontal bar)
    steer_center = w // 2
    steer_width = w // 3
    steer_pos = int(steer_center + (angle * steer_width / 90))  # 90 derajat = full width
    cv2.rectangle(image, (steer_center - steer_width//2, h - 80), 
                 (steer_center + steer_width//2, h - 100), (255, 255, 255), 2)
    cv2.circle(image, (steer_pos, h - 90), 8, (0, 0, 255), -1)
    
    # Instruksi
    cv2.putText(image, "Kontrol Direct Motor:", (w - 250, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
    cv2.putText(image, "- Tangan atas/bawah = kecepatan", (w - 300, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
    cv2.putText(image, "- Miring kiri/kanan = belok", (w - 250, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
    cv2.putText(image, "- Kepal tangan = mundur", (w - 230, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)

def main():
    """Main function untuk menjalankan hand control direct motor"""
    try:
        print("Hand Control Direct Motor - Press Q to exit")
        print("- Kontrol langsung nilai motor A dan B")
        print("- Motor A (kanan), Motor B (kiri)")
        print("- Gerakkan tangan untuk differential steering")
        print("- Kepal tangan untuk mode mundur")
        
        while cap.isOpened():
            success, image = cap.read()
            if not success:
                print("Ignoring empty camera frame.")
                continue
                
            # Flip image for selfie view
            # image = cv2.flip(image, 1)
            h, w, _ = image.shape
            
            # Convert to RGB for MediaPipe
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            results = hands.process(image_rgb)
            
            # Tambahkan grid referensi
            cv2.line(image, (w//2, 0), (w//2, h), (100, 100, 100), 1)
            cv2.line(image, (0, h//2), (w, h//2), (100, 100, 100), 1)
            
            if results.multi_hand_landmarks:
                for hand_landmarks in results.multi_hand_landmarks:
                    # Gambar landmarks
                    mp_drawing.draw_landmarks(
                        image, 
                        hand_landmarks, 
                        mp_hands.HAND_CONNECTIONS,
                        mp_drawing_styles.get_default_hand_landmarks_style(),
                        mp_drawing_styles.get_default_hand_connections_style())
                    
                    # Ambil koordinat landmark
                    landmarks = hand_landmarks.landmark
                    wrist = landmarks[0]      # WRIST
                    middle_mcp = landmarks[9] # MIDDLE_MCP
                    
                    # Deteksi tangan tertutup
                    hand_closed = is_hand_closed(landmarks)
                    
                    # Hitung pusat telapak tangan
                    palm_x, palm_y = calculate_palm_center(landmarks)
                    
                    # Hitung sudut steering menggunakan titik 0 dan 9
                    direction_vector = [middle_mcp.x - wrist.x, middle_mcp.y - wrist.y]
                    angle = math.degrees(math.atan2(direction_vector[0], -direction_vector[1]))
                    angle = angle + 10
                    # Hitung nilai motor
                    raw_motorA, raw_motorB = calculate_motor_values(palm_x, palm_y, angle, hand_closed)
                    
                    # Smoothing
                    motorA = int(smooth_value(raw_motorA, motorA_history))
                    motorB = int(smooth_value(raw_motorB, motorB_history))
                    
                    # Kirim nilai ke ESP32
                    send_motor_values(motorA, motorB)
                    
                    # Visualisasi kontrol
                    draw_control_indicators(image, motorA, motorB, angle, hand_closed)
                    
                    # Visualisasi garis steering
                    wrist_px = int(wrist.x * w)
                    wrist_py = int(wrist.y * h)
                    middle_px = int(middle_mcp.x * w)
                    middle_py = int(middle_mcp.y * h)
                    cv2.line(image, (wrist_px, wrist_py), (middle_px, middle_py), (255, 0, 0), 4)
                    
                    # Debug: Gambar titik-titik jari untuk melihat deteksi
                    finger_tips = [4, 8, 12, 16, 20]  # THUMB, INDEX, MIDDLE, RING, PINKY tips
                    finger_colors = [(255, 0, 255), (0, 255, 255), (255, 255, 0), (255, 0, 0), (0, 0, 255)]
                    for i, tip_idx in enumerate(finger_tips):
                        tip = landmarks[tip_idx]
                        tip_px = int(tip.x * w)
                        tip_py = int(tip.y * h)
                        cv2.circle(image, (tip_px, tip_py), 8, finger_colors[i], -1)
                        cv2.putText(image, str(tip_idx), (tip_px + 10, tip_py), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, finger_colors[i], 1)
                    
            else:
                # Jika tidak ada tangan terdeteksi, hentikan motor
                send_motor_values(0, 0)
                cv2.putText(image, "Tangan tidak terdeteksi - STOP", (w//2 - 150, h//2), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
            
            cv2.imshow('ESP32 Direct Motor Control', image)
            if cv2.waitKey(5) & 0xFF == ord('q'):
                break

    finally:
        cap.release()
        cv2.destroyAllWindows()
        # Stop motors when closing
        sock.sendto("0,0".encode(), (UDP_IP, UDP_PORT))
        print("Stopped motors and closed application")

if __name__ == "__main__":
    main()
