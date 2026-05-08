import asyncio
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

async def test():
    print("Testing DialogGPT Load...")
    model_name = "microsoft/DialoGPT-small"
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(model_name)
    
    print("Model Loaded. Testing generation...")
    text = "Hello! How are you?"
    input_ids = tokenizer.encode(text + tokenizer.eos_token, return_tensors='pt')
    
    chat_history_ids = model.generate(
        input_ids, 
        max_length=1000, 
        pad_token_id=tokenizer.eos_token_id
    )
    
    response = tokenizer.decode(
        chat_history_ids[:, input_ids.shape[-1]:][0], 
        skip_special_tokens=True
    )
    
    print(f"User: {text}")
    print(f"Bot: {response}")

if __name__ == "__main__":
    asyncio.run(test())
