"""q411 Aurora Revision -- revise a worn crystal rule without assuming control reversibility."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,SKY,CURTAIN,CRYSTAL,WEAR,CONTROL,DELAY,RULE,BAD=12,10,15,14,11,9,6,0,8
LEVELS=[{"name":"Old Light","boundary":3,"mode":1,"plan":(1,2)},{"name":"Wear Curtain","boundary":2,"mode":2,"plan":(2,1,4)},{"name":"Inverted Mote","boundary":2,"mode":3,"plan":(3,2,5,1)},{"name":"Hysteresis Rule","boundary":3,"mode":2,"plan":(1,4,5,2,3)},{"name":"Delayed Revision","boundary":2,"mode":1,"plan":(2,3,4,1,5,2)},{"name":"Aurora Revision","boundary":3,"mode":3,"plan":(3,1,5,2,4,3,1,5)}]
def advance(s,a,x):
 crystals,wear,control,direction,delay=s;crystals=list(crystals)
 if a in (1,2,3):
  i=a-1;rule=1 if wear<x["boundary"] else x["mode"]
  if rule==1:crystals[i]=(crystals[i]+a+control)%4
  elif rule==2:crystals[i]=3-crystals[i]
  else:delay=(delay+a+i)%4
  wear+=1
 elif a==4:
  control=(control+direction)%3
  if control in (0,2):direction=-direction
 elif a==5:crystals=[(v+delay+control)%4 for v in crystals];delay=0
 return tuple(crystals),wear,control,direction,delay
def target(x):
 s=((0,1,2),0,0,1,0)
 for a in x["plan"]:s=advance(s,a,x)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=SKY;f[8:17,8:56]=CURTAIN
  for i,v in enumerate(g.crystals):x=9+i*18;f[23:37,x:x+12]=CRYSTAL;f[27+v*3:32+v*3,x+3:x+9]=RULE
  f[43:46,8:8+min(g.wear,8)*6]=WEAR;f[49:52,8:8+g.control*14]=CONTROL;f[55:58,8:8+g.delay*12]=DELAY
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q411(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q411",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.crystals=(0,1,2);self.wear=self.control=self.delay=0;self.direction=1
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.crystals,self.wear,self.control,self.direction,self.delay=advance((self.crystals,self.wear,self.control,self.direction,self.delay),a,x)
  elif a==6:
   if (self.crystals,self.wear,self.control,self.direction,self.delay)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
