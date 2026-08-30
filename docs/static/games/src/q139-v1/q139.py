"""q139 Clock-Skew Messages -- messages encode content and two delivery phases."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,CLOCK,SENDER,RECEIVER,CONTENT,MESSAGE,DONE,BAD=0,7,9,12,14,10,6,8
LEVELS=[
 {"name":"Delivery Phase","mods":[2,3],"messages":[[0,1,2]]},
 {"name":"Clock Skew","mods":[3,4],"messages":[[1,2,1],[0,0,3]]},
 {"name":"Encode the Cycle","mods":[4,5],"messages":[[2,3,2],[1,1,4]]},
 {"name":"Two Phase Address","mods":[5,6],"messages":[[1,4,1],[2,2,5],[0,0,3]]},
 {"name":"Asynchronous Syntax","mods":[6,7],"messages":[[2,5,4],[0,1,6],[1,4,2]]},
 {"name":"Clock-Skew Messages","mods":[7,8],"messages":[[1,6,3],[2,2,7],[0,5,1],[2,0,6]]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=CLOCK;f[15:27,8:22]=SENDER;f[15:27,42:56]=RECEIVER;f[31:37,8:8+g.phase[0]*6]=MESSAGE;f[39:45,8:8+g.phase[1]*5]=MESSAGE;f[48:52,8:18+g.content*12]=CONTENT
  for i in range(len(g.messages)):f[3:6,8+i*8:14+i*8]=DONE if i<g.progress else MESSAGE
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q139(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.mods=self.messages=[];self.phase=[0,0];self.content=self.progress=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q139",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.mods=list(s["mods"]);self.messages=[list(x) for x in s["messages"]];self.phase=[0,0];self.content=self.progress=0;self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z==1:self.phase[0]=(self.phase[0]+1)%self.mods[0]
  elif z==2:self.phase[1]=(self.phase[1]+1)%self.mods[1]
  elif z==3:self.content=(self.content-1)%3
  elif z==4:self.content=(self.content+1)%3
  elif z==5:
   if [self.content,*self.phase]!=self.messages[self.progress]:self.failed=True;self.lose()
   else:
    self.progress+=1
    if self.progress==len(self.messages):self.next_level()
  self.complete_action()
