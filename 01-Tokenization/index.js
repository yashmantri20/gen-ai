import { encoding_for_model } from "tiktoken";

const enc = encoding_for_model("gpt-4o");

const text = "Hello, I am Yash";
const tokens = enc.encode(text);

console.log("Tokens:", tokens);

const myTokens = [13225, 11, 357, 939, 865, 1229];
const decodedUint8Array = enc.decode(myTokens);

// Convert Uint8Array to string
const decodedText = new TextDecoder("utf-8").decode(decodedUint8Array);

enc.free();

console.log("Decoded Text:", decodedText);
