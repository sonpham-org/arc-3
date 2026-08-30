"""q245 Trust Auction -- infer bidder roles as bids rewrite shared capital."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,MARKET,BIDDER,BID,ROLE,TRUST,CAPITAL,BAD=1,13,15,14,11,10,12,8
BASE=((1,2,3),(2,3,1),(3,1,2))
LEVELS=[
 {"name":"First Bid","role":0,"trust":0,"need":(1,)},{"name":"Paired Lot","role":1,"trust":0,"need":(1,2)},
 {"name":"Changing Capital","role":2,"trust":1,"need":(2,3)},{"name":"Joint Auction","role":1,"trust":2,"need":(1,2,3)},
 {"name":"Counter Bid","role":0,"trust":2,"need":(3,1,2)},{"name":"Trust Auction","role":2,"trust":1,"need":(2,3,1,2)}]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=MARKET
  for i in range(3):
   x=9+i*17;f[11:24,x:x+11]=BID if g.seen&(1<<i) else BIDDER
  for i,v in enumerate(g.bids[-5:]):f[30+i*4:33+i*4,8:8+v*9]=BID
  f[49:52,8:8+g.capital*9]=CAPITAL;f[53:56,8:8+g.role*13]=ROLE;f[57:60,8:8+g.trust*13]=TRUST
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q245(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.seen=self.role=self.trust=self.capital=0;self.history=[];self.bids=[];self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q245",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.seen=self.role=self.trust=self.capital=0;self.history=[];self.bids=[];self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3):
   self.seen|=1<<(a-1);self.history.append(a);bid=(BASE[x["role"]][a-1]+self.capital+x["trust"])%5;self.bids.append(bid);self.capital=(self.capital+2*bid+a)%5
  elif a==4:self.role=(self.role+1)%3
  elif a==5:self.trust=(self.trust+1)%3
  elif a==6:
   if tuple(self.history)==x["need"] and (self.role,self.trust)==(x["role"],x["trust"]):self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
