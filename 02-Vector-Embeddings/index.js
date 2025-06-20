import OpenAI from 'openai';
import dotenv from 'dotenv';
dotenv.config();

const client = new OpenAI({
    apiKey: process.env['OPENAI_API_KEY'],
});
  
const text = "dog chases cat"
const response = await client.embeddings.create({
    model: 'text-embedding-3-small',
    input: text,
  });

console.log("Vector Embeddings", response)
console.log(response.data[0].embedding?.length)


