"""q239 Chorus Market -- infer both a public norm and a trust regime."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,MARKET,STALL,VOICE,NORM,TRUST,BAD=1,14,12,15,11,9,8
SIGNALS=(((1,2,1),(2,1,2),(1,1,3)),((2,3,1),(1,2,3),(3,1,2)),((3,1,2),(2,3,1),(1,2,2)))
LEVELS=[
 {"name":"First Bid","norm":0,"trust":0,"need":(1,)},
 {"name":"Trusted Pair","norm":1,"trust":0,"need":(1,2)},
 {"name":"Rumor Stall","norm":2,"trust":1,"need":(2,3)},
 {"name":"Public Chorus","norm":1,"trust":2,"need":(1,2,3)},
 {"name":"Counterfeit Trust","norm":0,"trust":2,"need":(1,3,2)},
 {"name":"Chorus Market","norm":2,"trust":1,"need":(3,1,2,3)}]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=MARKET
  for i in range(3):
   x=9+i*17;f[11:23,x:x+11]=VOICE if g.seen&(1<<i) else STALL
  for i,v in enumerate(g.transcript[-5:]):f[29+i*4:32+i*4,8:8+v*10]=TRUST
  f[51:55,8:8+g.norm*13]=NORM;f[56:59,8:8+g.trust*13]=TRUST
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q239(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.seen=self.norm=self.trust=0;self.history=[];self.transcript=[];self.bad=False
  levels=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS]
  super().__init__("q239",levels,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.seen=self.norm=self.trust=0;self.history=[];self.transcript=[];self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3):self.seen|=1<<(a-1);self.history.append(a);self.transcript.append(SIGNALS[x["trust"]][x["norm"]][a-1])
  elif a==4:self.norm=(self.norm+1)%3
  elif a==5:self.trust=(self.trust+1)%3
  elif a==6:
   if tuple(self.history)==x["need"] and (self.norm,self.trust)==(x["norm"],x["trust"]):self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
