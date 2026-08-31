"""q382 Tide Delegation -- integrate disjoint controller marks before irreversible handoff."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,BASIN,CURRENT,SHELL,VIEW,MARK,CONTROL,COMMIT,BAD=6,10,9,14,12,5,11,7,15
LEVELS=[{"name":"Split Current","plan":(1,3,4,2,3,5)},{"name":"Remote Shell","plan":(2,3,4,1,3,5)},{"name":"Alternating Marks","plan":(1,2,3,4,2,3,5)},{"name":"One-Way Handoff","plan":(2,1,3,4,1,2,3,5)},{"name":"Reverse Evidence","plan":(1,3,4,2,1,3,4,2,3,5)},{"name":"Tide Delegation","plan":(2,1,3,4,1,3,4,2,3,5)}]
def advance(s,a):
 controller,views,marks,direction,committed=s;views=list(views);marks=list(marks)
 if committed>=0:return None
 if a in (1,2):views[controller]|=1<<((controller+a+(1 if direction>0 else 2))%4)
 elif a==3:marks[controller]=(views[controller]*3+controller+(1 if direction>0 else 2))%8
 elif a==4:controller=1-controller;direction=-direction
 elif a==5:committed=(marks[0]^marks[1]^(1 if direction>0 else 2))%8
 return controller,tuple(views),tuple(marks),direction,committed
def target(x):
 s=(0,(0,0),(0,0),1,-1)
 for a in x["plan"]:s=advance(s,a);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=BASIN;f[8:15,8:56]=CURRENT
  for i,v in enumerate(g.views):x=7+i*28;f[20:39,x:x+22]=SHELL-i;f[24:31,x+4:x+4+max(1,v)*3]=VIEW;f[42:45,x:x+max(1,g.marks[i])*3]=MARK
  f[50:53,8:11+g.controller*22]=CONTROL;f[56:59,8:20]=COMMIT if g.committed>=0 else CURRENT
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q382(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q382",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.controller=0;self.views=(0,0);self.marks=(0,0);self.direction=1;self.committed=-1
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.controller,self.views,self.marks,self.direction,self.committed),a)
   if s is None:self.bad=True;self.lose()
   else:self.controller,self.views,self.marks,self.direction,self.committed=s
  elif a==6:
   if (self.controller,self.views,self.marks,self.direction,self.committed)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
