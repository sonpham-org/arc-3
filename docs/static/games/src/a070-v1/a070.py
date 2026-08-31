"""a070 Exposure Window -- trade instantaneous position for motion-smear evidence."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,DARKROOM,TRACK,OBJECT_A,OBJECT_B,CAMERA,SMEAR,GATE,EXPOSE,BAD=14,8,9,12,10,4,11,13,6,15
LEVELS=[
 {"name":"Short Exposure","seq":(1,)},{"name":"Lengthen Exposure","seq":(2,)},
 {"name":"Read Smear","seq":(2,4)},{"name":"Compare Speeds","seq":(1,4,2,4,3)},
 {"name":"Match Gate","seq":(2,2,4,3,1,4,3)},{"name":"Exposure Window","seq":(1,4,2,4,2,3,4,1,3,4)},
]
def advance(s,a):
 positions,speeds,exposure,smears,gate,clock,history,snapshot=s;p=list(positions)
 if a==1:exposure=1;history=(history+(1,))[-8:]
 elif a==2:exposure=1+exposure%4;history=(history+(2,))[-8:]
 elif a==3:gate=(gate+1)%3;history=(history+(3,))[-8:]
 elif a==4:
  smears=tuple(min(8,v*exposure) for v in speeds);p=[(p[i]+speeds[i]*exposure)%12 for i in range(2)];clock=(clock+exposure)%12;history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(p),speeds,exposure,smears,gate,clock,history)
 return tuple(p),speeds,exposure,smears,gate,clock,history,snapshot
for x in LEVELS:
 s=((1,7),(1,3),1,(0,0),0,0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=DARKROOM
  for i,col in enumerate((OBJECT_A,OBJECT_B)):
   y=16+i*22;f[y:y+10,7:57]=TRACK;x=8+g.positions[i]*4;f[y-2:y+12,x:x+5]=col
   if g.smears[i]:f[y+3:y+7,max(7,x-g.smears[i]*3):x]=SMEAR
  f[8:13,8:8+g.exposure*10]=EXPOSE;f[7:16,49:57]=CAMERA
  for i in range(3):f[53:58,8+i*17:20+i*17]=GATE if i==g.gate else TRACK
  if g.bad:f[1:4,18:46]=BAD
  return f
class A070(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a070",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.positions,self.speeds,self.exposure,self.smears,self.gate,self.clock,self.history,self.snapshot=((1,7),(1,3),1,(0,0),0,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.positions,self.speeds,self.exposure,self.smears,self.gate,self.clock,self.history,self.snapshot=advance((self.positions,self.speeds,self.exposure,self.smears,self.gate,self.clock,self.history,self.snapshot),a)
  elif a==6:
   if (self.positions,self.speeds,self.exposure,self.smears,self.gate,self.clock,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
