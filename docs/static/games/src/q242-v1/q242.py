"""q242 Choir Tokens -- infer a role and key as questioning rewrites a shared token."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,HALL,SINGER,VOICE,ROLE,KEY,TOKEN,BAD=1,13,15,12,14,10,11,8
BASE=((1,2,3),(2,3,1),(3,1,2))
LEVELS=[
 {"name":"First Voice","role":0,"key":0,"need":(1,)},{"name":"Paired Chorus","role":1,"key":0,"need":(1,2)},
 {"name":"Changing Token","role":2,"key":1,"need":(2,3)},{"name":"Joint Refrain","role":1,"key":2,"need":(1,2,3)},
 {"name":"Counter Melody","role":0,"key":2,"need":(3,1,2)},{"name":"Choir Tokens","role":2,"key":1,"need":(2,3,1,2)}]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=HALL
  for i in range(3):
   x=9+i*17;f[11:24,x:x+11]=VOICE if g.seen&(1<<i) else SINGER
  for i,v in enumerate(g.transcript[-5:]):f[30+i*4:33+i*4,8:8+v*10]=VOICE
  f[49:52,8:8+g.token*10]=TOKEN;f[53:56,8:8+g.role*13]=ROLE;f[57:60,8:8+g.key*13]=KEY
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q242(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.seen=self.role=self.key=self.token=0;self.history=[];self.transcript=[];self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q242",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.seen=self.role=self.key=self.token=0;self.history=[];self.transcript=[];self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3):
   self.seen|=1<<(a-1);self.history.append(a);reply=(BASE[x["role"]][a-1]+self.token+x["key"])%4;self.transcript.append(reply);self.token=(self.token+reply+a)%4
  elif a==4:self.role=(self.role+1)%3
  elif a==5:self.key=(self.key+1)%3
  elif a==6:
   if tuple(self.history)==x["need"] and (self.role,self.key)==(x["role"],x["key"]):self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
