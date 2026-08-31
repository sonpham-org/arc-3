"""q682 Tide Evidence -- stop unequal current sampling before an irreversible gate."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,BASIN,SHELL,CURRENT,SAMPLE,MARGIN,COST,GOAL,BAD=6,11,14,10,8,12,9,13,15
LEVELS=[
 {"name":"One Reading","seq":(1,)},{"name":"Reverse Sample","seq":(2,1)},
 {"name":"Current Shift","seq":(3,1,2)},{"name":"Bounded Margin","seq":(1,3,2,1)},
 {"name":"Costly Evidence","seq":(2,3,1,2,3,1)},
 {"name":"Tide Evidence","seq":(1,2,3,1,3,2,1,2,3)}]
def advance(s,a):
 current,phase,samples,margin,cost,stopped=s
 if a==1:margin+=2+phase;samples=samples+((current,phase,1),);cost+=1
 elif a==2:margin-=1+current;samples=samples+((current,phase,-1),);cost+=2
 elif a==3:current^=1;phase=(phase+1+current)%4;margin+=phase-1
 elif a==4:margin=max(-12,min(12,2*margin));cost+=1
 elif a==5:stopped=(current,phase,samples[-4:],margin,cost,int(abs(margin)>cost//3))
 return current,phase,samples,margin,cost,stopped
for x in LEVELS:
 s=(0,0,(),0,0,None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=BASIN
  for i in range(6):x=8+i*8;f[9:29,x:x+6]=CURRENT;f[22-(i%3)*5:27-(i%3)*5,x+1:x+5]=SHELL
  for i,(_,p,sign) in enumerate(g.samples[-5:]):x=8+i*10;f[35:41,x:x+7]=SAMPLE if sign>0 else COST;f[42:45,x:x+2+p]=CURRENT
  center=31;lo=max(5,min(center,center+g.margin));hi=min(58,max(center,center+g.margin));f[49:54,lo:hi+1]=MARGIN
  f[55:59,8:8+min(g.cost,10)*4]=COST
  if g.stopped:f[52:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q682(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"]
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q682",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.current=self.phase=self.margin=self.cost=0;self.samples=();self.stopped=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.current,self.phase,self.samples,self.margin,self.cost,self.stopped=advance((self.current,self.phase,self.samples,self.margin,self.cost,self.stopped),a)
  elif a==6:
   if (self.current,self.phase,self.samples,self.margin,self.cost,self.stopped)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
