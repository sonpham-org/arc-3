"""a031 Branching Actuator -- infer lever mode while consequences reshape branch geometry."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,WORKS,BRANCH,LEVER,NEAR,FAR,MODE,GOAL,BAD=0,10,8,14,11,12,6,13,15
LEVELS=[{"name":"Near Consequence","seq":(1,3)},{"name":"Far Consequence","seq":(2,3)},{"name":"Mode Contrast","seq":(1,2,3)},{"name":"Geometry Shift","seq":(4,2,1,3)},{"name":"Entangled Actuator","seq":(2,3,1,4,2,1,3)},{"name":"Branching Actuator","seq":(1,2,3,4,1,3,2,4,1,3)}]
def advance(s,a):
 mode,near,far,geometry,evidence,resolved=s
 if a==1:
  if mode==0:near=(near+1+geometry)%7
  else:far=(far-1-geometry)%7
  mode^=1;geometry=(geometry+near+far)%4
 elif a==2:
  if mode==0:far=(far+2)%7
  else:near=(near-2)%7
  mode^=1;geometry=(geometry+1)%4
 elif a==3:evidence=evidence+((mode,near,far,geometry),)
 elif a==4:geometry=(geometry+2)%4;near,far=far,near
 elif a==5:resolved=(mode,near,far,geometry,evidence[-4:])
 return mode,near,far,geometry,evidence,resolved
for x in LEVELS:
 s=(0,1,5,0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=WORKS;f[28:34,8:56]=BRANCH;f[16:46,29:35]=LEVER
  f[10+g.near*4:16+g.near*4,9:25]=NEAR;f[10+g.far*4:16+g.far*4,39:55]=FAR
  for i,_ in enumerate(g.evidence[-4:]):f[48:53,8+i*12:17+i*12]=MODE
  if g.resolved:f[51:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class A031(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a031",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.mode=0;self.near=1;self.far=5;self.geometry=0;self.evidence=();self.resolved=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.mode,self.near,self.far,self.geometry,self.evidence,self.resolved=advance((self.mode,self.near,self.far,self.geometry,self.evidence,self.resolved),a)
  elif a==6:
   if (self.mode,self.near,self.far,self.geometry,self.evidence,self.resolved)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
