"""q412 Tide Revision -- recalibrate a worn current before irreversible repair."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,BASIN,CURRENT,SHELL,WEAR,RULE,DELAY,COMMIT,BAD=7,10,9,14,12,5,11,6,15
LEVELS=[{"name":"Old Current","boundary":3,"mode":1,"plan":(1,2,5)},{"name":"Wear Reversal","boundary":2,"mode":2,"plan":(2,1,4,5)},{"name":"Delayed Shell","boundary":2,"mode":3,"plan":(3,2,1,5)},{"name":"One-Way Repair","boundary":3,"mode":2,"plan":(1,4,2,3,5)},{"name":"Sparse Calibration","boundary":2,"mode":1,"plan":(2,3,4,1,2,5)},{"name":"Tide Revision","boundary":3,"mode":3,"plan":(3,1,4,2,3,1,5)}]
def advance(s,a,x):
 shells,wear,current,direction,delay,sealed=s;shells=list(shells)
 if sealed:return None
 if a in (1,2,3):
  i=a-1;rule=1 if wear<x["boundary"] else x["mode"]
  if rule==1:shells[i]=(shells[i]+a+current)%4
  elif rule==2:shells[i]=3-shells[i]
  else:delay=(delay+a+i+current)%4
  wear+=1
 elif a==4:
  current=(current+direction)%3
  if current in (0,2):direction=-direction
 elif a==5:shells=[(v+delay+current)%4 for v in shells];delay=0;sealed=True
 return tuple(shells),wear,current,direction,delay,sealed
def target(x):
 s=((0,1,2),0,0,1,0,False)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=BASIN;f[8:15,8:56]=CURRENT
  for i,v in enumerate(g.shells):x=9+i*18;f[20:37,x:x+12]=SHELL-i;f[24+v*3:29+v*3,x+3:x+9]=RULE
  f[42:45,8:11+min(g.wear,7)*6]=WEAR;f[49:52,8:11+g.current*14]=CURRENT;f[55:58,8:11+g.delay*11]=DELAY;f[58:60,48:56]=COMMIT if g.sealed else CURRENT
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q412(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q412",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.shells=(0,1,2);self.wear=self.current=self.delay=0;self.direction=1;self.sealed=False
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.shells,self.wear,self.current,self.direction,self.delay,self.sealed),a,x)
   if s is None:self.bad=True;self.lose()
   else:self.shells,self.wear,self.current,self.direction,self.delay,self.sealed=s
  elif a==6:
   if (self.shells,self.wear,self.current,self.direction,self.delay,self.sealed)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
