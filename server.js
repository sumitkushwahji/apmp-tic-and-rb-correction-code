const { SerialPort } = require('serialport');
const { Server } = require('socket.io');
const http = require('http');

// Create an HTTP server to attach `socket.io` to
const server = http.createServer((req, res) => {
  res.writeHead(200, { 'Content-Type': 'text/plain' });
  res.end('Socket.IO server running\n');
});

// Initialize socket.io server on port 3000
const io = new Server(server, {
  cors: {
    origin: '*', // Adjust this to your frontend's address if needed
    methods: ['GET', 'POST']
  },
});

// Configure the serial port (COM11, 115200 baud)
const port = new SerialPort({
  path: 'COM14',
  baudRate: 115200,
  autoOpen: true,
});

port.on('error', (err) => {
  console.error('Error opening port:', err.message);
});

// Buffer for accumulating partial data
let buffer = '';

// Read data from the serial port and broadcast to all connected WebSocket clients
port.on('data', (data) => {
  buffer += data.toString();

  // Check if the buffer contains a full message (assume '\n' as the message delimiter)
  let index;
  while ((index = buffer.indexOf('\n')) >= 0) {
    const message = buffer.slice(0, index).trim();
    buffer = buffer.slice(index + 1);

    const timestampedMessage = {
      timestamp: new Date().toISOString(), // Adjust the format as needed
      value: message,
    };

    console.log('TIC Data:', timestampedMessage);

    // Emit the data to all connected clients
    io.emit('message', timestampedMessage);
  }
});

io.on('connection', (socket) => {
  console.log('Client connected');

  socket.on('disconnect', () => {
    console.log('Client disconnected');
  });
});

// Start the server
server.listen(3000, () => {
  console.log('Server running on http://localhost:3000');
});
