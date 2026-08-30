"""q244 Rumor Potluck -- infer host roles as each speaker rewrites the rumor."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,TABLE,GUEST,VOICE,ROLE,KEY,RUMOR,BAD=1,12,15,14,11,10,13,8
BASE=((1,2,3),(2,3,1),(3,1,2))
LEVELS=[
 {"name":"First Dish","role":0,"key":0,"need":(1,)},{"name":"Shared Course","role":1,"key":0,"need":(1,2)},
 {"name":"Changed Rumor","role":2,"key":1,"need":(2,3)},{"name":"Joint Table","role":1,"key":2,"need":(1,2,3)},
 {"name":"Counter Story","role":0,"key":2,"need":(3,1,2)},{"name":"Rumor Potluck","role":2,"key":1,"need":(2,3,1,2)}]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=TABLE
  for i in range(3):
   x=9+i*17;f[11:24,x:x+11]=VOICE if g.seen&(1<<i) else GUEST
  for i,v in enumerate(g.transcript[-5:]):f[30+i*4:33+i*4,8:8+v*9]=VOICE
  f[49:52,8:8+g.rumor*9]=RUMOR;f[53:56,8:8+g.role*13]=ROLE;f[57:60,8:8+g.key*13]=KEY
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q244(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.seen=self.role=self.key=self.rumor=0;self.history=[];self.transcript=[];self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q244",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.seen=self.role=self.key=self.rumor=0;self.history=[];self.transcript=[];self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3):
   self.seen|=1<<(a-1);self.history.append(a);reply=(BASE[x["role"]][a-1]+self.rumor+x["key"])%5;self.transcript.append(reply);self.rumor=(2*self.rumor+reply+a)%5
  elif a==4:self.role=(self.role+1)%3
  elif a==5:self.key=(self.key+1)%3
  elif a==6:
   if tuple(self.history)==x["need"] and (self.role,self.key)==(x["role"],x["key"]):self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
