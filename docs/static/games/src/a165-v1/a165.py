"""a165 Landmark Search -- navigate repetitive junctions with relational distance bands."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,MAP,JUNCTION,LANDMARK_A,LANDMARK_B,BAND,TRAVELER,CHOICE,GOAL,STEPS=1,8,7,12,14,10,13,11,4,6
BAD=15
LEVELS=[
 {"name":"Choose Landmark","seq":(1,)},{"name":"Advance Junction","seq":(2,)},
 {"name":"Change Distance Band","seq":(3,1)},{"name":"Triangulate Goal","seq":(1,2,3,4,2)},
 {"name":"Ignore Repetition","seq":(1,3,2,1,4,3,2)},{"name":"Landmark Search","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 landmark,position,band,steps,distance,history,snapshot=s
 if a==1:landmark=1-landmark;history=(history+(1,))[-8:]
 elif a==2:position=(position+(1 if landmark==0 else 3))%12;steps=(steps+1)%10;history=(history+(2,))[-8:]
 elif a==3:band=(band+1)%4;history=(history+(3,))[-8:]
 elif a==4:target=10;distance=min((position-target)%12,(target-position)%12)+abs(band-(2 if landmark else 1));history=(history+(4,))[-8:]
 elif a==5:snapshot=(landmark,position,band,steps,distance,history)
 return landmark,position,band,steps,distance,history,snapshot
for q in LEVELS:
 s=(0,0,0,0,5,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=MAP
  for i in range(12):x=8+(i%4)*13;y=11+(i//4)*15;f[y:y+11,x:x+11]=JUNCTION
  f[11:22,8:19]=LANDMARK_A;f[41:52,47:58]=LANDMARK_B;px=10+(g.position%4)*13;py=13+(g.position//4)*15;f[py:py+7,px:px+7]=TRAVELER;f[54:58,8:8+g.band*10]=BAND;f[7:10,8:8+g.distance*6]=GOAL;f[54:58,50:50+g.steps*2]=STEPS
  if g.bad:f[1:4,18:46]=BAD
  return f
class A165(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a165",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.landmark,self.position,self.band,self.steps,self.distance,self.history,self.snapshot=(0,0,0,0,5,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.landmark,self.position,self.band,self.steps,self.distance,self.history,self.snapshot=advance((self.landmark,self.position,self.band,self.steps,self.distance,self.history,self.snapshot),a)
  elif a==6:
   if (self.landmark,self.position,self.band,self.steps,self.distance,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
