"""q164 Stop Test -- stop sampling once remaining evidence cannot change the best choice."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,LAB,SAMPLE,HIDDEN,CHOICE,COST,DONE,BAD=12,1,9,3,10,8,14,13
LEVELS=[
 {"name":"Certain Lead","seq":[1,1,2],"stop":2,"choice":1}, {"name":"One More Test","seq":[2,1,2,2],"stop":3,"choice":2},
 {"name":"Cannot Change","seq":[3,3,1,2,3],"stop":3,"choice":3}, {"name":"Costly Sequence","seq":[1,2,1,3,1,1],"stop":5,"choice":1},
 {"name":"Late Certainty","seq":[4,2,4,3,4,1,4],"stop":6,"choice":4}, {"name":"Stop Test","seq":[2,3,2,1,2,4,2,2],"stop":7,"choice":2}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:55,4:60]=LAB
  for i,a in enumerate(g.seq):x=7+i*6;f[19:27,x:x+4]=SAMPLE if i<g.seen else HIDDEN;f[21:24,x:x+a]=CHOICE if i<g.seen else HIDDEN
  f[37:43,7:7+g.seen*6]=COST;f[47:51,7:7+g.stop*6]=DONE
  if g.failed:f[59:63,25:39]=BAD
  return f
class Q164(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.seq=[];self.stop=self.choice=self.seen=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q164",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5])
 def on_set_level(self,l):s=LEVELS[self.level_index];self.seq=list(s["seq"]);self.stop=s["stop"];self.choice=s["choice"];self.seen=0;self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a==5 and self.seen<len(self.seq):self.seen+=1
  elif 1<=a<=4:
   if self.seen==self.stop and a==self.choice:self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()
