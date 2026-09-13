"""
Sample Audio Generator
Generates sample .wav tracks using pure Python (wave + math)
No extra dependencies required!
"""
import os
import wave
import struct
import math

def generate_tone_sequence(filename, notes_with_durations, sample_rate=44100):
    """
    notes_with_durations: list of (freq_hz, duration_sec)
    """
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    
    total_samples = []
    for freq, duration in notes_with_durations:
        num_samples = int(sample_rate * duration)
        for i in range(num_samples):
            t = float(i) / sample_rate
            # Add an envelope to prevent clicking
            envelope = min(1.0, i / 500) * min(1.0, (num_samples - i) / 500)
            if freq == 0:
                sample = 0
            else:
                sample = envelope * math.sin(2.0 * math.pi * freq * t)
            # 16-bit audio
            int_sample = int(sample * 30000)
            total_samples.append(int_sample)
            
    with wave.open(filename, 'w') as wav_file:
        wav_file.setnchannels(1)       # Mono
        wav_file.setsampwidth(2)      # 2 bytes per sample (16-bit)
        wav_file.setframerate(sample_rate)
        packed_data = struct.pack(f'<{len(total_samples)}h', *total_samples)
        wav_file.writeframes(packed_data)
    print(f"Generated sample sound: {filename}")

def generate_all_samples():
    music_dir = os.path.join(os.path.dirname(__file__), "music")
    
    # Track 1: Happy Arpeggio (C - E - G - C5)
    t1 = os.path.join(music_dir, "song1.wav")
    if not os.path.exists(t1):
        melody1 = [
            (261.63, 0.2), # C4
            (329.63, 0.2), # E4
            (392.00, 0.2), # G4
            (523.25, 0.4), # C5
            (392.00, 0.2), # G4
            (523.25, 0.6), # C5
        ]
        generate_tone_sequence(t1, melody1)

    # Track 2: Chime / Victory Tone (G - C - E - G5)
    t2 = os.path.join(music_dir, "song2.wav")
    if not os.path.exists(t2):
        melody2 = [
            (392.00, 0.15), # G4
            (523.25, 0.15), # C5
            (659.25, 0.15), # E5
            (783.99, 0.5),  # G5
        ]
        generate_tone_sequence(t2, melody2)

    # Track 3: Energetic Game Tone (A minor riff)
    t3 = os.path.join(music_dir, "song3.wav")
    if not os.path.exists(t3):
        melody3 = [
            (440.00, 0.18), # A4
            (493.88, 0.18), # B4
            (523.25, 0.18), # C5
            (587.33, 0.18), # D5
            (659.25, 0.4),  # E5
            (440.00, 0.5),  # A4
        ]
        generate_tone_sequence(t3, melody3)

if __name__ == "__main__":
    generate_all_samples()
