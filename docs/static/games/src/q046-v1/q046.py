"""q046 One Question -- choose one binary test that identifies the hidden rule."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,LAB,RULE,TEST,YES,NO,CURSOR,BAD=4,1,10,12,14,8,11,13
LEVELS=[
 {"name":"Binary Split","rules":2,"target":1,"tests":[1]}, {"name":"Choose Question","rules":3,"target":2,"tests":[1,2]},
 {"name":"Balanced Partition","rules":4,"target":3,"tests":[3,5,10]}, {"name":"One Bit","rules":5,"target":1,"tests":[3,12,18]},
 {"name":"Informative Test","rules":6,"target":4,"tests":[7,25,42,52]}, {"name":"One Question","rules":7,"target":5,"tests":[15,51,85,102]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[7:56,4:60]=LAB
  for i in range(g.rules):x=7+i*7;f[16:27,x:x+5]=RULE;f[12:15,x:x+5]=CURSOR if i==g.hyp else LAB
  for i,t in enumerate(g.tests):x=8+i*12;f[38:45,x:x+9]=TEST;f[47:51,x:x+9]=YES if g.asked and g.answer else NO if g.asked else LAB;f[34:37,x:x+9]=CURSOR if i==g.cursor else LAB
  if g.failed:f[59:63,25:39]=BAD
  return f
class Q046(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.rules=self.target=self.cursor=self.hyp=0;self.tests=[];self.asked=False;self.answer=False;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q046",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5,6])
 def on_set_level(self,l):s=LEVELS[self.level_index];self.rules=s["rules"];self.target=s["target"];self.tests=list(s["tests"]);self.cursor=self.hyp=0;self.asked=False;self.answer=False;self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a==1:self.hyp=(self.hyp-1)%self.rules
  elif a==2:self.hyp=(self.hyp+1)%self.rules
  elif a==3:self.cursor=(self.cursor-1)%len(self.tests)
  elif a==4:self.cursor=(self.cursor+1)%len(self.tests)
  elif a==5 and not self.asked:self.answer=bool(self.tests[self.cursor]&(1<<self.target));self.asked=True
  elif a==6:
   if self.asked and self.hyp==self.target:self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()
