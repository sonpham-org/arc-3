"""q241 Festival Oaths -- infer roles from path-dependent public replies."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FESTIVAL,ENVOY,REPLY,ROLE,MOOD,BAD=1,12,15,14,11,10,8
BASE=((1,2,3),(2,3,1),(3,1,2))
LEVELS=[
 {"name":"First Oath","role":0,"mood":0,"need":(1,)},{"name":"Echoed Promise","role":1,"mood":0,"need":(1,2)},
 {"name":"Changed Witness","role":2,"mood":1,"need":(2,3)},{"name":"Procession Pact","role":1,"mood":2,"need":(1,2,3)},
 {"name":"Path Dependence","role":0,"mood":2,"need":(3,1,2)},{"name":"Festival Oaths","role":2,"mood":1,"need":(2,3,1,2)}]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=FESTIVAL
  for i in range(3):
   x=9+i*17;f[11:24,x:x+11]=REPLY if g.seen&(1<<i) else ENVOY
  for i,v in enumerate(g.transcript[-5:]):f[30+i*4:33+i*4,8:8+v*10]=REPLY
  f[52:55,8:8+g.role*13]=ROLE;f[56:59,8:8+g.mood*13]=MOOD
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q241(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.seen=self.role=self.mood=self.reply_phase=0;self.history=[];self.transcript=[];self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q241",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.seen=self.role=self.mood=self.reply_phase=0;self.history=[];self.transcript=[];self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3):
   self.seen|=1<<(a-1);self.history.append(a);self.transcript.append((BASE[x["role"]][a-1]+self.reply_phase+x["mood"])%4);self.reply_phase=(self.reply_phase+a)%3
  elif a==4:self.role=(self.role+1)%3
  elif a==5:self.mood=(self.mood+1)%3
  elif a==6:
   if tuple(self.history)==x["need"] and (self.role,self.mood)==(x["role"],x["mood"]):self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
