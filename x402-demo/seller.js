import express from "express";
import { paymentMiddleware } from "x402-express";
// import { facilitator } from "@coinbase/x402"; // For mainnet

const app = express();

app.use(paymentMiddleware(
  "0xdB772823f62c009E6EC805BC57A4aFc7B2701F1F", // receiving wallet address
  {  // Route configurations for protected endpoints
    "GET /weather": {
      // USDC amount in dollars
      price: "$0.001",
      network: "polygon-amoy",
      asset: "0x41E94Eb019C0762f9Bfcf9Fb1E58725BfB0e7582", // USDC contract address
      // Optional: Add metadata for better discovery in x402 Bazaar
      config: {
        description: "Get current weather data for any location",
        inputSchema: {
          type: "object",
          properties: {
            location: { type: "string", description: "City name" }
          }
        },
        outputSchema: {
          type: "object",
          properties: {
            weather: { type: "string" },
            temperature: { type: "number" }
          }
        }
      }
    },
  },
  {
    url: process.env.FACILITATOR_URL || "https://x402.polygon.technology", // Polygon Amoy facilitator
  }
));

let server;

// Handle cleanup on exit
function cleanup() {
  if (server) {
    server.close(() => {
      console.log('Server shutdown complete');
      process.exit(0);
    });
    
    // Force close after 2 seconds if graceful shutdown fails
    setTimeout(() => {
      console.log('Forcing server shutdown');
      process.exit(1);
    }, 2000);
  }
}

// Handle different ways the program might terminate
process.on('SIGINT', cleanup);  // Ctrl+C
process.on('SIGTERM', cleanup); // Kill
process.on('uncaughtException', (err) => {
  console.error('Uncaught exception:', err);
  cleanup();
});

// Implement your route
app.get("/weather", (req, res) => {
  const paymentHeader = req.get('x-payment-response');
  
  res.json({
    weather: "sunny",
    temperature: 70
  });

  if (paymentHeader) {
    console.log('Transaction completed successfully!');
    console.log('Payment details:', paymentHeader);
    console.log('Server will stop after response is sent...');
    
    // Gracefully shutdown after response is sent
    res.on('finish', () => {
      cleanup();
    });
  }
});

// Try to find an available port starting from 4021
function startServer(port) {
  server = app.listen(port, () => {
    console.log(`Server listening at http://localhost:${port}`);
    console.log('Waiting for transaction... (Press Ctrl+C to stop)');
  }).on('error', (err) => {
    if (err.code === 'EADDRINUSE') {
      console.log(`Port ${port} is busy, trying ${port + 1}...`);
      startServer(port + 1);
    } else {
      console.error('Server error:', err);
      process.exit(1);
    }
  });
}

startServer(4021);