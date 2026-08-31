"""q384 Honeycomb Delegation -- integrate remote marks while local and hive clocks diverge."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,APIARY,CELL,COURIER,VIEW,MARK,LOCAL,GLOBAL,BAD=11,9,14,5,12,4,6,7,15
LEVELS=[{"name":"Split Scent","cycle":2,"plan":(1,3,4,2,3,5)},{"name":"Remote Courier","cycle":2,"plan":(2,3,4,1,3,5)},{"name":"Alternating Marks","cycle":3,"plan":(1,2,3,4,2,3,5)},{"name":"Two-Clock Relay","cycle":3,"plan":(2,1,3,4,1,2,3,5)},{"name":"Nested Handoff","cycle":4,"plan":(1,3,4,2,1,3,4,2,3,5)},{"name":"Honeycomb Delegation","cycle":4,"plan":(2,1,3,4,1,3,4,2,3,5)}]
def advance(s,a,x):
 controller,views,marks,local,global_,integrated=s;views=list(views);marks=list(marks)
 if a in (1,2):views[controller]|=1<<((controller+a+local+global_)%4)
 elif a==3:marks[controller]=(views[controller]*3+local+global_+controller)%8
 elif a==4:controller=1-controller
 elif a==5:integrated=(marks[0]^marks[1]^local^global_)%8
 local+=1
 if local>=x["cycle"]:local=0;global_=(global_+1)%4
 return controller,tuple(views),tuple(marks),local,global_,integrated
def target(x):
 s=(0,(0,0),(0,0),0,0,0)
 for a in x["plan"]:s=advance(s,a,x)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=APIARY;f[8:15,8:56]=CELL
  for i,v in enumerate(g.views):x=7+i*28;f[20:39,x:x+22]=COURIER+i;f[24:31,x+4:x+4+max(1,v)*3]=VIEW;f[42:45,x:x+max(1,g.marks[i])*3]=MARK
  f[50:53,8:11+g.controller*22]=MARK;f[54:57,8:11+g.local*11]=LOCAL;f[58:60,8:11+g.global_*11]=GLOBAL
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q384(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q384",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.controller=0;self.views=(0,0);self.marks=(0,0);self.local=self.global_=self.integrated=0
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.controller,self.views,self.marks,self.local,self.global_,self.integrated=advance((self.controller,self.views,self.marks,self.local,self.global_,self.integrated),a,x)
  elif a==6:
   if (self.controller,self.views,self.marks,self.local,self.global_,self.integrated)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
