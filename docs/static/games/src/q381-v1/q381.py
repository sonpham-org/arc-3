"""q381 Aurora Delegation -- combine controller marks through a hysteretic curtain."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,SKY,CURTAIN,MOTE,CONTROL,MARK,HYST,INTEGRATE,BAD=7,10,15,14,12,6,9,11,8
LEVELS=[{"name":"Split Light","plan":(1,3,4,2,3,5)},{"name":"Remote Curtain","plan":(2,3,4,1,3,5)},{"name":"Alternating Marks","plan":(1,2,3,4,2,3,5)},{"name":"Hysteretic View","plan":(2,1,3,4,1,2,3,5)},{"name":"Return Sweep","plan":(1,3,4,2,1,3,5,4,2)},{"name":"Aurora Delegation","plan":(2,1,3,4,1,3,5,4,2,3,5)}]
def advance(s,a):
 controller,views,marks,control,direction,integrated=s;views=list(views);marks=list(marks)
 if a in (1,2):views[controller]|=1<<((controller+a+control)%4)
 elif a==3:marks[controller]=(views[controller]*3+control+controller+1)%8
 elif a==4:controller=1-controller
 elif a==5:
  control=(control+direction)%3
  if control in (0,2):direction=-direction
  integrated=(marks[0]^marks[1]^control)%8
 return controller,tuple(views),tuple(marks),control,direction,integrated
def target(x):
 s=(0,(0,0),(0,0),0,1,0)
 for a in x["plan"]:s=advance(s,a)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=SKY;f[8:17,8:56]=CURTAIN
  for i,v in enumerate(g.views):f[22+i*15:30+i*15,8:8+max(1,v)*4]=MOTE;f[31+i*15:34+i*15,8:8+max(1,g.marks[i])*5]=MARK
  f[53:56,8:8+g.controller*22]=CONTROL;f[57:59,8:8+g.control*14]=HYST;f[59:61,8:8+g.integrated*6]=INTEGRATE
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q381(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q381",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.controller=0;self.views=(0,0);self.marks=(0,0);self.control=0;self.direction=1;self.integrated=0
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.controller,self.views,self.marks,self.control,self.direction,self.integrated=advance((self.controller,self.views,self.marks,self.control,self.direction,self.integrated),a)
  elif a==6:
   if (self.controller,self.views,self.marks,self.control,self.direction,self.integrated)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
