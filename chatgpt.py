import openai

class ChatBot:
    def __init__(self, api_key = None):
        if api_key == None:
            exit()
        self.client = openai.OpenAI(api_key = api_key)
        # モデルはお好みでgpt-4o番台とかに変えてもOK
        self.model = "gpt-4-turbo"
        self.messages = []

    def set_system_setting(self, system_setting):
        self.messages.append({"role": "system", "content": system_setting})

    def chat(self, message):
        self.messages.append({"role": "user", "content": message})
        response = self.client.chat.completions.create(model=self.model, messages=self.messages)
        ans = response.choices[0].message.content
        self.messages.append({"role": "assistant", "content": ans})
        return ans

    # 1回きりの質問（game.py側でaskが使われていた場合用）
    def ask(self, system_setting, prompt):
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_setting},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content

    def reset_messages(self):
        self.messages = []

    def get_messages(self):
        return self.messages
