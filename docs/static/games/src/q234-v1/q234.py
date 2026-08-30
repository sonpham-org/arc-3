"""q234 Honeycomb Pact -- infer a convention whose replies depend on two clocks."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,HIVE,CELL,OFFER,REPLY,LOCAL,OUTER,BAD=4,11,9,14,15,12,6,8
LEVELS=[
 {"name":"Scent Convention","rule":0,"cycle":2},{"name":"Local Reply","rule":1,"cycle":3},
 {"name":"Outer Reply","rule":2,"cycle":2},{"name":"Reciprocal Clock","rule":1,"cycle":4},
 {"name":"Joint Commitment","rule":2,"cycle":3},{"name":"Honeycomb Pact","rule":0,"cycle":5}]
def response(rule,offer,outer):return ((offer-1+rule*(outer+1))%3)+1
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[5:59,4:60]=HIVE
  for x in (9,25,41):f[15:28,x:x+12]=CELL
  f[34:39,8:8+g.seen*9]=OFFER;f[41:46,8:8+len(g.replies)*11]=REPLY;f[49:52,8:8+g.local*8]=LOCAL;f[54:57,8:8+g.outer*9]=OUTER
  if g.bad:f[61:64,22:42]=BAD
  return f
class Q234(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.rule=self.cycle=self.local=self.outer=self.seen=self.candidate=0;self.replies=[];self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q234",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,5])
 def on_set_level(self,l):x=LEVELS[self.level_index];self.rule=x["rule"];self.cycle=x["cycle"];self.local=self.outer=self.seen=self.candidate=0;self.replies=[];self.bad=False
 def tick(self):
  self.local+=1
  if self.local==self.cycle:self.local=0;self.outer=(self.outer+1)%3
 def fail(self):self.bad=True;self.lose()
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z in (1,2):self.replies.append(response(self.rule,z,self.outer));self.seen|=1<<(z-1);self.tick()
  elif z==3:self.candidate=(self.candidate+1)%3;self.tick()
  elif z==5:
   if self.seen==3 and self.candidate==self.rule:self.next_level()
   else:self.fail()
  else:self.fail()
  self.complete_action()
