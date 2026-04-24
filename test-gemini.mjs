import { GoogleGenAI } from './openclaw/node_modules/@google/genai/dist/index.mjs';

const ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });
try {
  const res = await ai.models.generateContent({
    model: 'gemini-2.5-flash',
    contents: '你好，用中文介绍一下自己'
  });
  console.log('SUCCESS:', res.text);
} catch (e) {
  console.error('ERROR:', e.message);
}
