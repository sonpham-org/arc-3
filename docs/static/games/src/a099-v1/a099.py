"""a099 Phase Cancel -- cancel at a bridge while reinforcing a gate."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,FIELD,SOURCE_A,SOURCE_B,WAVE,BRIDGE,GATE,CANCEL,REINFORCE,BAD=11,8,12,14,9,4,13,10,6,15
LEVELS=[
 {"name":"Shift Source A","seq":(1,)},{"name":"Shift Source B","seq":(2,)},
 {"name":"Advance Waves","seq":(1,3)},{"name":"Measure Sites","seq":(1,2,3,4,3)},
 {"name":"Cancel Bridge","seq":(1,2,3,4,2,3,4)},{"name":"Phase Cancel","seq":(1,3,2,3,4,1,2,3,4,3)},
]
def advance(s,a):
 phases,time,bridge,gate,traces,history,snapshot=s;p=list(phases)
 if a==1:p[0]=(p[0]+1)%4;history=(history+(1,))[-8:]
 elif a==2:p[1]=(p[1]+1)%4;history=(history+(2,))[-8:]
 elif a==3:time=(time+1)%12;traces=(traces+(((p[0]+time)%4,(p[1]+time)%4),))[-8:];history=(history+(3,))[-8:]
 elif a==4:bridge=abs(((p[0]+time)%4)-((p[1]+time+2)%4));gate=4-abs(((p[0]+time+1)%4)-((p[1]+time+1)%4));history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(p),time,bridge,gate,traces,history)
 return tuple(p),time,bridge,gate,traces,history,snapshot
for x in LEVELS:
 s=((0,0),0,0,0,(),(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=FIELD;f[22:42,7:15]=SOURCE_A;f[22:42,49:57]=SOURCE_B
  for i,(a,b) in enumerate(g.traces):x=17+i*4;f[28-a*3:31+a*3,x:x+2]=WAVE;f[32-b*3:35+b*3,x+2:x+4]=WAVE
  f[17:23,27:39]=BRIDGE;f[43:50,27:39]=GATE
  f[8:12,8:8+g.bridge*8]=CANCEL;f[52:56,8:8+g.gate*8]=REINFORCE
  f[13:17,8:20]=SOURCE_A;f[13:17,44:56]=SOURCE_B
  if g.bad:f[1:4,18:46]=BAD
  return f
class A099(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a099",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.phases,self.time,self.bridge,self.gate,self.traces,self.history,self.snapshot=((0,0),0,0,0,(),(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.phases,self.time,self.bridge,self.gate,self.traces,self.history,self.snapshot=advance((self.phases,self.time,self.bridge,self.gate,self.traces,self.history,self.snapshot),a)
  elif a==6:
   if (self.phases,self.time,self.bridge,self.gate,self.traces,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
