"""q136 Lossy Channel -- learn a redundant code for a predictably dropped signal class."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,CHANNEL,SENDER,RECEIVER,DROPPED,CODE,DONE,BAD=12,1,9,14,8,15,10,6
LEVELS=[
 {"name":"Dropped Symbol","drop":2,"target":[1,2]}, {"name":"Redundant Pair","drop":3,"target":[3,1,4]},
 {"name":"Mixed Message","drop":1,"target":[2,1,4,3]}, {"name":"Spatial Redundancy","drop":4,"target":[4,2,1,4,3]},
 {"name":"Do Not Repeat Blindly","drop":2,"target":[1,2,3,2,4,1]}, {"name":"Lossy Channel","drop":3,"target":[3,1,4,2,3,2,1]}]
def survivor_code(symbol,drop):
 if symbol!=drop:return[symbol]
 alt=drop%4+1;return[alt,alt]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=CHANNEL;f[16:29,8:20]=SENDER;f[36:49,8:20]=RECEIVER;f[3:6,8:8+g.drop*8]=DROPPED
  for i,t in enumerate(g.target):x=25+i*5;f[20:27,x:x+4]=CODE;f[39:46,x:x+4]=DONE if i<g.progress else RECEIVER
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q136(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.target=[];self.drop=self.progress=0;self.buffer=[];self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q136",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.target=list(s["target"]);self.drop=s["drop"];self.progress=0;self.buffer=[];self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z!=self.drop:self.buffer.append(z)
  expected=survivor_code(self.target[self.progress],self.drop)
  if self.buffer!=expected[:len(self.buffer)]:self.failed=True;self.lose()
  elif self.buffer==expected:
   self.progress+=1;self.buffer=[]
   if self.progress==len(self.target):self.next_level()
  self.complete_action()
