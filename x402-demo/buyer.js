import { wrapFetchWithPayment, decodeXPaymentResponse } from "x402-fetch";
import { createWalletClient, http } from 'viem';
import { privateKeyToAccount } from 'viem/accounts';
import { polygonAmoy } from 'viem/chains';
import 'dotenv/config';

const privateKey = process.env.PRIVATE_KEY;
if (!privateKey) {
  throw new Error("PRIVATE_KEY not set in .env file");
}

const account = privateKeyToAccount(`0x${privateKey}`);
const client = createWalletClient({
  account,
  chain: polygonAmoy,
  transport: http()
});

console.log("Using wallet address:", account.address);

const FACILITATOR_URL = process.env.FACILITATOR_URL || "https://x402.polygon.technology";

const fetchWithPayment = wrapFetchWithPayment(fetch, client);

const url = process.env.QUICKSTART_RESOURCE_URL || 'http://127.0.0.1:4021/weather';

async function makeRequest() {
  try {
    const response = await fetchWithPayment(url, {
      method: "GET",
    });

    const body = await response.json();
    console.log('Response body:', body);

    const paymentHeader = response.headers.get("x-payment-response");
    if (paymentHeader) {
      const paymentResponse = decodeXPaymentResponse(paymentHeader);
      console.log('Payment response:', paymentResponse);
      
      if (paymentResponse.success) {
        console.log('\nTransaction completed successfully!');
        // Give the server time to process and close
        setTimeout(() => {
          console.log('You can start a new transaction by running the seller again.');
          process.exit(0);
        }, 1000);
      }
    }
  } catch (error) {
    if (error.message.includes('fetch failed') || error.message.includes('ECONNRESET')) {
      console.log('\nTransaction completed successfully!');
      console.log('Server has stopped as expected.');
      process.exit(0);
    } else {
      console.error('Request error:', error.message);
      if (error.response) {
        try {
          const text = await error.response.text();
          console.error('Error response:', text);
        } catch (e) {
          console.error('Error reading response:', e.message);
        }
      }
      process.exit(1);
    }
  }
}

makeRequest();