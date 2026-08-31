"""a004 Stuck Gear Census -- compare multiple inputs to separate backlash from a jammed axle."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,WALL,GEAR,AXLE,INPUT,MOTION,BACKLASH,GOAL,BAD=3,10,8,14,6,11,12,13,15
LEVELS=[{"name":"First Input","seq":(1,3)},{"name":"Opposite Wheel","seq":(2,3)},{"name":"Backlash Pause","seq":(1,2,3)},{"name":"Phase Reversal","seq":(4,2,1,3)},{"name":"Branch Census","seq":(2,3,1,4,2,1,3)},{"name":"Stuck Gear Census","seq":(1,2,3,4,1,3,2,4,1,3)}]
def advance(s,a):
 phase,input_id,jam,evidence,backlash,removed=s
 if a==1:input_id=(input_id-1)%3;phase=(phase+1)%5;backlash^=1
 elif a==2:input_id=(input_id+1)%3;phase=(phase+2)%5;backlash=(backlash+phase)%2
 elif a==3:motion=tuple(int(i!=jam and ((i-input_id)%3!=1 or not backlash)) for i in range(6));evidence=evidence+((input_id,phase,backlash,motion),)
 elif a==4:phase=(phase+3)%5;backlash=0
 elif a==5:removed=(jam,input_id,phase,evidence[-4:])
 return phase,input_id,jam,evidence,backlash,removed
for x in LEVELS:
 s=(0,0,4,(),0,None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=WALL;motion=g.evidence[-1][3] if g.evidence else (1,)*6
  for i,on in enumerate(motion):x=8+(i%3)*18;y=8+(i//3)*15;f[y:y+11,x:x+12]=GEAR if on else BACKLASH;f[y+3:y+8,x+4:x+8]=AXLE
  for i,(j,_,b,_) in enumerate(g.evidence[-4:]):x=8+i*12;f[41:47,x:x+9]=INPUT;f[48:51,x:x+2+j*2]=MOTION;f[52:54,x:x+2+b*3]=BACKLASH
  f[55:59,8:8+g.phase*8+7]=INPUT
  if g.removed:f[51:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class A004(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a004",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.phase=self.input_id=self.backlash=0;self.jam=4;self.evidence=();self.removed=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.phase,self.input_id,self.jam,self.evidence,self.backlash,self.removed=advance((self.phase,self.input_id,self.jam,self.evidence,self.backlash,self.removed),a)
  elif a==6:
   if (self.phase,self.input_id,self.jam,self.evidence,self.backlash,self.removed)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
