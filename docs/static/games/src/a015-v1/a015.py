"""a015 Calibration Crew -- alternate coupled adjustments within a one-turn tolerance."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,LAB,MACHINE,DIAL,MEASURE,SAFE,ACTIVE,GOAL,BAD=4,10,14,8,6,11,12,13,15
LEVELS=[{"name":"Cross Measure","seq":(1,)},{"name":"First Adjustment","seq":(2,1)},{"name":"Alternate Crew","seq":(3,1,2)},{"name":"Tolerance Turn","seq":(4,2,1,3)},{"name":"Coupled Range","seq":(2,3,1,4,2,1)},{"name":"Calibration Crew","seq":(1,2,3,4,1,3,2,4,1)}]
def advance(s,a):
 values,active,measurements,outside,turn,calibrated=s;v=list(values)
 if a==1:measurements=measurements+((active,v[active^1],turn),)
 elif a==2:v[active]=(v[active]+1+v[active^1]%2)%7;outside+=int(v[active] not in (2,3,4))
 elif a==3:active^=1;turn+=1;outside=max(0,outside-1)
 elif a==4:v[active]=(v[active]-2)%7;v[active^1]=(v[active^1]+1)%7;turn+=1
 elif a==5:calibrated=(tuple(v),active,measurements[-4:],outside,turn)
 return tuple(v),active,measurements,outside,turn,calibrated
for x in LEVELS:
 s=((1,5),0,(),0,0,None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=LAB
  for i,v in enumerate(g.values):x=9+i*28;f[9:32,x:x+20]=MACHINE;f[14:27,x+4:x+16]=SAFE;f[24-v*2:27,x+6:x+14]=DIAL;f[10:13,x+5:x+15]=ACTIVE if i==g.active else MEASURE
  for i,(_,v,_) in enumerate(g.measurements[-4:]):x=8+i*12;f[38:44,x:x+9]=MEASURE;f[45:48,x:x+2+v]=DIAL
  f[52:56,8:8+min(5,g.outside)*9]=ACTIVE
  if g.calibrated:f[51:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class A015(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a015",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.values=(1,5);self.active=0;self.measurements=();self.outside=self.turn=0;self.calibrated=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.values,self.active,self.measurements,self.outside,self.turn,self.calibrated=advance((self.values,self.active,self.measurements,self.outside,self.turn,self.calibrated),a)
  elif a==6:
   if (self.values,self.active,self.measurements,self.outside,self.turn,self.calibrated)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
