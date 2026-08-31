"""q709 Monsoon Evidence -- calibrate storm evidence at unequal clock phases."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,GARDEN,CLOUD,RAIN,SAMPLE,FAST,SLOW,GOAL,BAD=2,10,11,14,6,8,12,13,15
LEVELS=[{"name":"Rain Sample","seq":(1,)},{"name":"Delayed Cell","seq":(2,1)},{"name":"Unequal Clocks","seq":(3,1,2)},{"name":"Phase Pair","seq":(4,2,1,3)},{"name":"Costed Forecast","seq":(2,3,1,4,2,1)},{"name":"Monsoon Evidence","seq":(1,2,3,4,1,3,2,4,1)}]
def advance(s,a):
 cell,fast,slow,reliability,samples,margin,stopped=s
 if a==1:w=1+int((fast,slow) in ((1,0),(3,2)));margin+=w;samples=samples+((cell,fast,slow,w),);cell=(cell+1+slow)%8;fast=(fast+1)%4;slow=(slow+int(fast==0))%5
 elif a==2:w=1+reliability;margin-=w;samples=samples+((cell,fast,slow,-w),);cell=(cell+2+fast)%8;fast=(fast+2)%4;slow=(slow+1)%5
 elif a==3:fast=(fast+1)%4;slow=(slow+2)%5;reliability=(reliability+int(fast==slow%4)+1)%3
 elif a==4:margin+=2 if (fast+slow+cell)%3==0 else -1;reliability=(reliability+1)%3
 elif a==5:stopped=(cell,fast,slow,reliability,samples[-5:],margin)
 return cell,fast,slow,reliability,samples,margin,stopped
for x in LEVELS:
 s=(0,0,0,0,(),0,None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=GARDEN
  for i in range(8):x=8+(i%4)*12;y=8+(i//4)*13;f[y:y+9,x:x+9]=CLOUD;f[y+2:y+7,x+2:x+7]=RAIN if i==g.cell else SLOW
  for i,(_,a,b,w) in enumerate(g.samples[-5:]):x=7+i*10;f[36:42,x:x+8]=SAMPLE;f[43:46,x:x+2+a*2]=FAST;f[47:49,x:x+2+b]=RAIN if w>0 else SLOW
  f[51:54,8:8+g.fast*11+8]=FAST;f[56:59,8:8+g.slow*9+7]=SLOW
  if g.stopped:f[51:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q709(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q709",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.cell=self.fast=self.slow=self.reliability=self.margin=0;self.samples=();self.stopped=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.cell,self.fast,self.slow,self.reliability,self.samples,self.margin,self.stopped=advance((self.cell,self.fast,self.slow,self.reliability,self.samples,self.margin,self.stopped),a)
  elif a==6:
   if (self.cell,self.fast,self.slow,self.reliability,self.samples,self.margin,self.stopped)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
