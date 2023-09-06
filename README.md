Use this tool to extract historical on-chain price data from an archive node. 

Shoutout to [Banteg](https://github.com/banteg) [(@bantg)](https://twitter.com/bantg) and [nymmrx](https://github.com/nymmrx) [(@nymmrx)](https://twitter.com/nymmrx) for their awesome work on [yearn-exporter](https://github.com/yearn/yearn-exporter) that made this library possible.

To install:
```
pip install ypricemagic
```

To use:
```
from ypricemagic import magic
magic.get_price(token,block)
```

Or:
```
from ypricemagic.magic import get_price
get_price(token,block)
```

You can also import protocol specific modules. For example:
```
from ypricemagic import uniswap
uniswap.get_price(token, block)
```
```
from ypricemagic.compound import get_price
get_price(compoundToken, block)
```

# trading example:

```
import openai
import cbpro
import requests
from typing import List
import numpy as np
import pandas as pd
import talib
```

```
class CryptoTradingBot:
    def __init__(self, openai_api_key: str, product_ids: List[str]):
        self.openai_api_key = openai_api_key
        self.product_ids = product_ids
        self.public_client = cbpro.PublicClient()

    def get_historical_data(self, product_id: str, granularity: int = 86400) -> pd.DataFrame:
        rates = self.public_client.get_product_historic_rates(product_id, granularity=granularity)
        df = pd.DataFrame(rates, columns=["time", "low", "high", "open", "close", "volume"])
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df.set_index("time", inplace=True)
        return df

    def generate_prediction(self, prompt: str, model: str = "text-davinci-002", tokens: int = 100) -> str:
        openai.api_key = self.openai_api_key
        response = openai.Completion.create(
            engine=model,
            prompt=prompt,
            max_tokens=tokens,
            n=1,
            stop=None,
            temperature=0.5,
        )
        return response.choices[0].text.strip()

    def technical_analysis(self, df: pd.DataFrame) -> pd.DataFrame:
        df["SMA"] = talib.SMA(df["close"], timeperiod=10)
        df["RSI"] = talib.RSI(df["close"], timeperiod=14)
        df["MACD"], df["MACD_signal"], _ = talib.MACD(df["close"], fastperiod=12, slowperiod=26, signalperiod=9)
        return df

    def make_recommendation(self, historical_data: pd.DataFrame, predictions: str) -> str:
        # Implement your own logic for generating recommendations based on historical data, predictions, and technical indicators.
        # You can use the provided technical_analysis method to add indicators to your historical data DataFrame.
        pass

    def main(self):
        for product_id in self.product_ids:
            historical_data = self.get_historical_data(product_id)
            historical_data = self.technical_analysis(historical_data)

            prompt = f"Based on the historical data and technical indicators of {product_id}, predict the future price movement: {historical_data.tail(10).to_dict()}"
            predictions = self.generate_prediction(prompt)

            recommendation = self.make_recommendation(historical_data, predictions)
            print(f"Recommendation for {product_id}: {recommendation}")

if __name__ == "__main__":
    openai_api_key = "your_openai_api_key"
    product_ids = ["BTC-USD", "ETH-USD", "LTC-USD"]

    trading_bot = CryptoTradingBot(openai_api_key, product_ids)
    trading_bot.main()
```
