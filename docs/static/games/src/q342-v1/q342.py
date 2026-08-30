"""q342 Semaphore Survey -- combine bounded observations from two miniature signal systems."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,CLIFF,FLAG,BEAM,KNOWN,SYSTEM,POLICY,BAD=4,12,15,14,11,10,9,8
MASKS=((0b001101011,0b110010101,0b101110000),(0b101010101,0b011101000,0b110001011))
LEVELS=[
 {"name":"First Signal","plan":(1,4,1),"policy":0},{"name":"Dual Beam","plan":(2,4,1),"policy":1},
 {"name":"Complement Tests","plan":(3,2,4,1),"policy":2},{"name":"Bounded Yard","plan":(1,4,3,2),"policy":1},
 {"name":"Shared Evidence","plan":(2,1,4,3,1),"policy":2},{"name":"Semaphore Survey","plan":(3,1,4,2,3,1),"policy":0}]
def simulate(plan):
 known=system=seen=0
 for a in plan:
  if a in (1,2,3):known|=MASKS[system][a-1];seen|=1<<system
  else:system^=1
 return known,system,seen
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=CLIFF
  for i in range(3):f[10:24,9+i*17:20+i*17]=FLAG if g.system==0 else BEAM
  for i in range(9):
   x=8+(i%3)*17;y=29+(i//3)*6;f[y:y+4,x:x+9]=KNOWN if g.known&(1<<i) else CLIFF
  f[49:53,8+g.system*31:25+g.system*31]=SYSTEM;f[54:58,8:8+g.policy*14]=POLICY
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q342(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.known=self.system=self.seen=self.policy=0;self.history=[];self.target=(0,0,0);self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q342",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.known=self.system=self.seen=self.policy=0;self.history=[];self.target=simulate(LEVELS[self.level_index]["plan"]);self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3):self.known|=MASKS[self.system][a-1];self.seen|=1<<self.system;self.history.append(a)
  elif a==4:self.system^=1;self.history.append(a)
  elif a==5:self.policy=(self.policy+1)%3
  elif a==6:
   if tuple(self.history)==x["plan"] and (self.known,self.system,self.seen)==self.target and self.seen==3 and self.policy==x["policy"]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
