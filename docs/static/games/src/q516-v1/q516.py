"""q516 Backstage Frame -- accumulate signed stage pressure through a rotating local frame."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,STAGE,CURTAIN,ACTOR,FRAME,POSITIVE,NEGATIVE,GOAL,BAD=0,13,6,14,10,11,9,12,15
LEVELS=[
 {"name":"First Cue","seq":(1,)},{"name":"Rotated Cue","seq":(2,1)},
 {"name":"Reverse Sightline","seq":(1,2,3,1)},{"name":"Moving Stage","seq":(2,1,4,2,1)},
 {"name":"Signed Pressure","seq":(1,2,1,3,4,1)},{"name":"Backstage Frame","seq":(2,1,2,4,3,1,4)}]
def advance(s,a,x):
 value,direction,frame,goal=s
 if a==1:value+=direction*(frame+1)
 elif a==2:
  frame=(frame+1)%4
  if frame==2:direction*=-1
 elif a==3:direction*=-1
 elif a==4:value+=direction*2
 elif a==5:
  if (value,direction,frame)!=x["target"]:return None
  goal=(value,direction,frame)
 return value,direction,frame,goal
for x in LEVELS:
 s=(0,1,0,None)
 for a in x["seq"]:s=advance(s,a,x);assert s is not None
 x["target"]=(s[0],s[1],s[2]);x["plan"]=x["seq"]+(5,)
def target(x):
 s=(0,1,0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=STAGE;f[8:31,8:56]=CURTAIN
  for i in range(4):f[11+i*4:14+i*4,11:53]=ACTOR if i==g.frame else CURTAIN
  center=32;width=min(abs(g.value),12)*2;f[37:42,center:center+width]=POSITIVE if g.value>=0 else NEGATIVE
  f[47:51,8:28]=POSITIVE if g.direction>0 else NEGATIVE;f[47:51,36:56]=FRAME
  if g.goal:f[54:59,39:56]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q516(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q516",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.value=0;self.direction=1;self.frame=0;self.goal=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.value,self.direction,self.frame,self.goal),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.value,self.direction,self.frame,self.goal=s
  elif a==6:
   if (self.value,self.direction,self.frame,self.goal)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
