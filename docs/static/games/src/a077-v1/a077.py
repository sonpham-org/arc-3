"""a077 Universal Joint -- align yokes for even phase transmission."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,BENCH,SHAFT_IN,SHAFT_OUT,YOKE,JOINT,POINTER,PHASE,SMOOTH,BAD=5,8,9,12,14,10,11,13,6,15
LEVELS=[
 {"name":"Rotate Input","seq":(1,)},{"name":"Change Bend","seq":(2,1)},
 {"name":"Align Yoke","seq":(3,1,1)},{"name":"Track Phase","seq":(1,2,3,1,4)},
 {"name":"Even Transfer","seq":(3,1,2,1,4,1,3)},{"name":"Universal Joint","seq":(1,2,1,3,1,4,2,1,3,1)},
]
def advance(s,a):
 input_phase,output_phase,bend,yokes,error,smooth,history,snapshot=s;y=list(yokes)
 if a==1:
  input_phase=(input_phase+1)%12;delta=1+int((input_phase+bend+y[0]-y[1])%4==0);output_phase=(output_phase+delta)%12;error=abs((input_phase-output_phase)%12);smooth=min(5,smooth+1) if delta==1 else 0;history=(history+(delta,))[-8:]
 elif a==2:bend=1+bend%3;history=(history+(2,))[-8:]
 elif a==3:y[1]=(y[1]+1)%4;history=(history+(3,))[-8:]
 elif a==4:y[0]=(y[0]+1)%4;history=(history+(4,))[-8:]
 elif a==5:snapshot=(input_phase,output_phase,bend,tuple(y),error,smooth,history)
 return input_phase,output_phase,bend,tuple(y),error,smooth,history,snapshot
for x in LEVELS:
 s=(0,0,1,(0,1),0,0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=BENCH;f[27:34,6:27]=SHAFT_IN;f[27-g.bend*4:34-g.bend*4,38:59]=SHAFT_OUT
  f[21:40,24:31]=YOKE;f[17-g.bend*3:38-g.bend*3,34:41]=YOKE;f[24:37,29:37]=JOINT
  xi=8+g.input_phase;xo=42+g.output_phase;f[19:25,xi:xi+4]=POINTER;f[38:44,xo:xo+4]=POINTER
  f[8:12,8:8+g.error*3]=PHASE
  for i in range(g.smooth):f[53:57,9+i*9:16+i*9]=SMOOTH
  if g.bad:f[1:4,18:46]=BAD
  return f
class A077(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a077",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.input_phase,self.output_phase,self.bend,self.yokes,self.error,self.smooth,self.history,self.snapshot=(0,0,1,(0,1),0,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.input_phase,self.output_phase,self.bend,self.yokes,self.error,self.smooth,self.history,self.snapshot=advance((self.input_phase,self.output_phase,self.bend,self.yokes,self.error,self.smooth,self.history,self.snapshot),a)
  elif a==6:
   if (self.input_phase,self.output_phase,self.bend,self.yokes,self.error,self.smooth,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
