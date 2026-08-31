"""a065 Wagon Wheel -- change strobe interval to disambiguate true rotation."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,STUDIO,WHEEL,SPOKE,STROBE,SAMPLE,FORWARD,REVERSE,COUPLE,BAD=9,8,4,12,14,10,13,11,6,15
LEVELS=[
 {"name":"First Sample","seq":(1,)},{"name":"Faster Strobe","seq":(2,1)},
 {"name":"Aliased Reverse","seq":(3,1,1)},{"name":"Infer Rotation","seq":(2,1,3,1,4)},
 {"name":"Correct Phase","seq":(1,2,1,3,1,4,1)},{"name":"Wagon Wheel","seq":(2,1,1,3,1,4,2,1,4,1)},
]
def advance(s,a):
 phase,speed,interval,clock,samples,coupled,history,snapshot=s
 if a==1:phase=(phase+speed*interval)%12;clock=(clock+interval)%12;samples=(samples+(phase,))[-6:];history=(history+(1,))[-8:]
 elif a==2:interval=max(1,interval-1);history=(history+(2,))[-8:]
 elif a==3:interval=1+interval%4;history=(history+(3,))[-8:]
 elif a==4:coupled=(phase,interval,tuple(samples));history=(history+(4,))[-8:]
 elif a==5:snapshot=(phase,speed,interval,clock,samples,coupled,history)
 return phase,speed,interval,clock,samples,coupled,history,snapshot
for x in LEVELS:
 s=(0,5,3,0,(),None,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=STUDIO;cx=32;cy=30
  f[10:50,12:52]=WHEEL;f[14:46,16:48]=STUDIO;f[27:34,29:36]=WHEEL
  dx=((0,8,12,15,16,15,12,8,0,-8,-12,-15)[g.phase]);dy=((16,15,12,8,0,-8,-12,-15,-16,-15,-12,-8)[g.phase]);steps=16
  for i in range(steps+1):x=cx+dx*i//steps;y=cy+dy*i//steps;f[y:y+3,x:x+3]=SPOKE
  f[7:11,8:8+g.interval*10]=STROBE
  for i,p in enumerate(g.samples):f[53:57,8+i*8:14+i*8]=FORWARD if p<6 else REVERSE
  if g.coupled:f[24:38,54:58]=COUPLE
  if g.bad:f[1:4,18:46]=BAD
  return f
class A065(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a065",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.phase,self.speed,self.interval,self.clock,self.samples,self.coupled,self.history,self.snapshot=(0,5,3,0,(),None,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.phase,self.speed,self.interval,self.clock,self.samples,self.coupled,self.history,self.snapshot=advance((self.phase,self.speed,self.interval,self.clock,self.samples,self.coupled,self.history,self.snapshot),a)
  elif a==6:
   if (self.phase,self.speed,self.interval,self.clock,self.samples,self.coupled,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
