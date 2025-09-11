from flask import Flask
import subprocess
import threading

app = Flask(__name__)

SOURCE_FILE = "input.mp4"  
DEST_STREAM_URL = "rtmp://localhost:1935/live/stream"

resolution_map = {
    240: '426x240',
    360: '640x360',
    480: '854x480',
    720: '1280x720',
    1080: '1920x1080',
    1440: '2560x1440',
    2160: '3840x2160',
}

@app.route('/stream/<int:resolution>/<int:duration>', methods=['GET'])
def push_stream(resolution, duration):
    def run_ffmpeg():
        command = [
            'ffmpeg', 
            '-re', 
            '-stream_loop', '-1',
            '-r', '24',
            '-i', SOURCE_FILE,
            '-t', str(duration),
            '-s', resolution_map[resolution],
            # '-vcodec', 'libx264', 
            '-f', 'flv',  
            DEST_STREAM_URL
        ]
        print("Running:", " ".join(command))

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,  
            bufsize=1
        )

        
        with process.stdout:
            for line in process.stdout:
                print("[ffmpeg]", line.strip())

        process.wait()

    threading.Thread(target=run_ffmpeg).start()
    return f"Streaming {duration}s video at {resolution}p to {DEST_STREAM_URL}", 200

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
