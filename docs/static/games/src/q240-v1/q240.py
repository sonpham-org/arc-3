"""q240 Embassy Masks -- infer protocol and witness reliability together."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,EMBASSY,MASK,VOICE,PROTOCOL,TRUST,BAD=1,7,15,12,14,11,8
SIGNALS=(((1,2,3),(2,1,2),(3,2,1)),((2,3,1),(1,3,2),(2,1,3)),((3,1,2),(3,2,1),(1,2,2)))
LEVELS=[
 {"name":"First Envoy","protocol":0,"trust":0,"need":(1,)},{"name":"Reliable Pair","protocol":1,"trust":0,"need":(1,2)},
 {"name":"Masked Witness","protocol":2,"trust":1,"need":(2,3)},{"name":"Joint Audience","protocol":1,"trust":2,"need":(1,2,3)},
 {"name":"False Credential","protocol":0,"trust":2,"need":(3,1,2)},{"name":"Embassy Masks","protocol":2,"trust":1,"need":(2,3,1,2)}]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=EMBASSY
  for i in range(3):
   x=9+i*17;f[11:24,x:x+11]=VOICE if g.seen&(1<<i) else MASK
  for i,v in enumerate(g.transcript[-5:]):f[30+i*4:33+i*4,8:8+v*10]=TRUST
  f[52:55,8:8+g.protocol*13]=PROTOCOL;f[56:59,8:8+g.trust*13]=TRUST
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q240(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.seen=self.protocol=self.trust=0;self.history=[];self.transcript=[];self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q240",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.seen=self.protocol=self.trust=0;self.history=[];self.transcript=[];self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3):self.seen|=1<<(a-1);self.history.append(a);self.transcript.append(SIGNALS[x["trust"]][x["protocol"]][a-1])
  elif a==4:self.protocol=(self.protocol+1)%3
  elif a==5:self.trust=(self.trust+1)%3
  elif a==6:
   if tuple(self.history)==x["need"] and (self.protocol,self.trust)==(x["protocol"],x["trust"]):self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
