"""a023 Dead Zone -- accumulate latent force before thresholded slider motion."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,CONSOLE,TRACK,SLIDER,FORCE,THRESHOLD,TRACE,GOAL,BAD=2,10,8,14,11,12,6,13,15
LEVELS=[{"name":"Silent Push","seq":(1,3)},{"name":"Second Slider","seq":(2,3)},{"name":"Threshold Jump","seq":(1,2,3)},{"name":"Force Reset","seq":(4,2,1,3)},{"name":"Collision Margin","seq":(2,3,1,4,2,1,3)},{"name":"Dead Zone","seq":(1,2,3,4,1,3,2,4,1,3)}]
def advance(s,a):
 positions,forces,thresholds,active,traces,aligned=s;p=list(positions);f=list(forces)
 if a==1:
  f[active]+=1
  if f[active]>=thresholds[active]:p[active]=(p[active]+f[active]-thresholds[active]+1)%8;f[active]=0
 elif a==2:active=(active+1)%3
 elif a==3:traces=traces+((tuple(p),tuple(f),active,thresholds[active]),)
 elif a==4:f[active]=0;p[active]=(p[active]-1)%8
 elif a==5:aligned=(tuple(p),tuple(f),thresholds,active,traces[-4:])
 return tuple(p),tuple(f),thresholds,active,traces,aligned
for x in LEVELS:
 s=((0,2,5),(0,0,0),(2,3,4),0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=CONSOLE
  for i,(p,z,t) in enumerate(zip(g.positions,g.forces,g.thresholds)):y=9+i*12;f[y:y+8,8:56]=TRACK;x=8+p*6;f[y:y+8,x:x+6]=SLIDER;f[y+9:y+12,8:8+z*9]=FORCE;f[y+9:y+12,48:48+t*2]=THRESHOLD
  for i,_ in enumerate(g.traces[-3:]):f[51:56,8+i*14:18+i*14]=TRACE
  if g.aligned:f[51:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class A023(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a023",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.positions=(0,2,5);self.forces=(0,0,0);self.thresholds=(2,3,4);self.active=0;self.traces=();self.aligned=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.positions,self.forces,self.thresholds,self.active,self.traces,self.aligned=advance((self.positions,self.forces,self.thresholds,self.active,self.traces,self.aligned),a)
  elif a==6:
   if (self.positions,self.forces,self.thresholds,self.active,self.traces,self.aligned)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
