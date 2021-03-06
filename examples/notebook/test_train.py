# %%
import sys; sys.path.append("/Users/fodrh1201/Workspace/tensortrade")
import pandas as pd
import tensortrade.env.default as default

from tensortrade.data.cdd import CryptoDataDownload
from tensortrade.feed.core import Stream, DataFeed
from tensortrade.oms.exchanges import Exchange
from tensortrade.oms.services.execution.simulated import execute_order
from tensortrade.oms.instruments import USD, BTC, ETH
from tensortrade.oms.wallets import Wallet, Portfolio
from tensortrade.agents import DQNAgent

# %%
cdd = CryptoDataDownload()

data = cdd.fetch("Bitstamp", "USD", "BTC", "1h")


# %%
def rsi(price: Stream[float], period: float) -> Stream[float]:
    r = price.diff()
    upside = r.clamp_min(0).abs()
    downside = r.clamp_max(0).abs()
    rs = upside.ewm(alpha=1 / period).mean() / downside.ewm(alpha=1 / period).mean()
    return 100*(1 - (1 + rs) ** -1)


def macd(price: Stream[float], fast: float, slow: float, signal: float) -> Stream[float]:
    fm = price.ewm(span=fast, adjust=False).mean()
    sm = price.ewm(span=slow, adjust=False).mean()
    md = fm - sm
    signal = md - md.ewm(span=signal, adjust=False).mean()
    return signal


features = []
for c in data.columns[1:]:
    s = Stream.source(list(data[c]), dtype="float").rename(data[c].name)
    features += [s]

cp = Stream.select(features, lambda s: s.name == "close")
op = Stream.select(features, lambda s: s.name == 'open')
hp = Stream.select(features, lambda s: s.name == 'high')
lp = Stream.select(features, lambda s: s.name == 'low')
v = Stream.select(features, lambda s: s.name == 'volume')

features = [
    cp.log().diff().rename("lr"),
    op.log().diff().rename("op"),
    hp.log().diff().rename("hp"),
    lp.log().diff().rename("lp"),
    v.log().diff().rename("v"),
    rsi(cp, period=20).rename("rsi"),
    macd(cp, fast=10, slow=50, signal=5).rename("macd"),
]

feed = DataFeed(features)
feed.compile()
# %%
bitstamp = Exchange("bitstamp", service=execute_order)(
    Stream.source(list(data["close"]), dtype="float").rename("USD-BTC")
)

portfolio = Portfolio(USD, [
    Wallet(bitstamp, 100000 * USD),
    Wallet(bitstamp, 10 * BTC)
])


renderer_feed = DataFeed([
    Stream.source(list(data["date"])).rename("date"),
    Stream.source(list(data["open"]), dtype="float").rename("open"),
    Stream.source(list(data["high"]), dtype="float").rename("high"),
    Stream.source(list(data["low"]), dtype="float").rename("low"),
    Stream.source(list(data["close"]), dtype="float").rename("close"), 
    Stream.source(list(data["volume"]), dtype="float").rename("volume") 
])


env = default.create(
    portfolio=portfolio,
    action_scheme="simple",
    reward_scheme="simple",
    feed=feed,
    renderer_feed=renderer_feed,
    renderer=default.renderers.ScreenLogger(),
    window_size=40
)
# %%
env.observer.feed.next()

# %%
agent = DQNAgent(env)

agent.train(n_steps=200, n_episodes=1000)
# %%
portfolio.ledger.as_frame()

# %%
portfolio.performance[0]
# %%
portfolio.performance[197]
# %%
portfolio.net_worth
# %%
