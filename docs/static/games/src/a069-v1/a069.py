"""a069 Sparse Tracker -- spend four observations to estimate a bouncing target."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,RANGE,TRACK,TARGET,SIGHT,CATCHER,BOUNCE,SAMPLE,FUTURE,BAD=13,8,9,12,14,10,11,6,4,15
LEVELS=[
 {"name":"First Sight","seq":(2,)},{"name":"Advance Target","seq":(1,2)},
 {"name":"Estimate Velocity","seq":(1,1,2,3)},{"name":"Account Bounce","seq":(1,1,1,2,3)},
 {"name":"Place Catcher","seq":(1,2,1,2,3,3,4)},{"name":"Sparse Tracker","seq":(1,2,1,1,2,3,1,3,4,2)},
]
def move(pos,vel):
 p=pos+vel;v=vel;b=0
 if p<0:p=-p;v=-v;b=1
 if p>11:p=22-p;v=-v;b=1
 return p,v,b
def advance(s,a):
 pos,vel,time,samples,catcher,bounces,caught,history,snapshot=s
 if a==1:pos,vel,b=move(pos,vel);time+=1;bounces=(bounces+b)%6;history=(history+(1,))[-8:]
 elif a==2:
  if len(samples)<4:samples=samples+((time,pos),)
  history=(history+(2,))[-8:]
 elif a==3:catcher=(catcher+1)%12;history=(history+(3,))[-8:]
 elif a==4:
  for _ in range(2):pos,vel,b=move(pos,vel);time+=1;bounces=(bounces+b)%6
  caught=int(catcher==pos);history=(history+(4,))[-8:]
 elif a==5:snapshot=(pos,vel,time,samples,catcher,bounces,caught,history)
 return pos,vel,time,samples,catcher,bounces,caught,history,snapshot
for x in LEVELS:
 s=(2,3,0,(),0,0,0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=RANGE;f[25:38,7:57]=TRACK
  x=8+g.pos*4;f[22:41,x:x+5]=TARGET
  cx=8+g.catcher*4;f[42:50,cx:cx+5]=CATCHER
  for i,(t,p) in enumerate(g.samples):sx=8+p*4;f[13+i*3:15+i*3,sx:sx+5]=SIGHT
  for i in range(g.bounces):f[53:57,8+i*6:13+i*6]=BOUNCE
  f[7:11,8:8+len(g.samples)*10]=SAMPLE
  if g.caught:f[52:58,48:57]=FUTURE
  if g.bad:f[1:4,18:46]=BAD
  return f
class A069(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a069",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.pos,self.velocity,self.time,self.samples,self.catcher,self.bounces,self.caught,self.history,self.snapshot=(2,3,0,(),0,0,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.pos,self.velocity,self.time,self.samples,self.catcher,self.bounces,self.caught,self.history,self.snapshot=advance((self.pos,self.velocity,self.time,self.samples,self.catcher,self.bounces,self.caught,self.history,self.snapshot),a)
  elif a==6:
   if (self.pos,self.velocity,self.time,self.samples,self.catcher,self.bounces,self.caught,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
