import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtNetwork import QLocalServer, QLocalSocket

app = QApplication(sys.argv)
socket = QLocalSocket()
socket.connectToServer("axiom_desktop_v3")

if socket.waitForConnected(500):
    print("Instance already running. Sending wakeup signal.")
    socket.write(b"WAKEUP")
    socket.waitForBytesWritten(1000)
    socket.disconnectFromServer()
    sys.exit(0)

print("First instance starting...")
server = QLocalServer()
server.removeServer("axiom_desktop_v3") # Cleanup stale socket
server.listen("axiom_desktop_v3")

def on_new_connection():
    sock = server.nextPendingConnection()
    if sock.waitForReadyRead(500):
        msg = sock.readAll().data()
        if msg == b"WAKEUP":
            print("Waking up main window!")
    sock.disconnectFromServer()

server.newConnection.connect(on_new_connection)
