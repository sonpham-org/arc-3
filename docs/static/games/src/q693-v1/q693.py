"""q693 Murmuration Evidence -- stop wind sampling only after a parity-consistent margin."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,AVIARY,FLOCK,WIND,SAMPLE,PARITY,MARGIN,GOAL,BAD=6,11,14,10,8,9,12,13,15
LEVELS=[{"name":"One Sample","seq":(1,)},{"name":"Reverse Wake","seq":(2,1)},{"name":"Parity Shift","seq":(3,1,2)},{"name":"Checked Margin","seq":(1,3,2,1)},{"name":"Costly Evidence","seq":(2,3,1,2,3,1)},{"name":"Murmuration Evidence","seq":(1,2,3,1,3,2,1,2,3)}]
def advance(s,a):
 wind,parity,samples,margin,cost,stopped=s
 if a==1:margin+=2+parity;samples=samples+((wind,parity,1),);cost+=1;wind=(wind+1)%4
 elif a==2:margin-=1+wind%2;samples=samples+((wind,parity,-1),);cost+=2;wind=(wind+2)%4
 elif a==3:parity^=(wind%2);margin+=1 if parity==0 else -1
 elif a==4:margin=max(-12,min(12,2*margin));cost+=1
 elif a==5:stopped=(wind,parity,samples[-4:],margin,cost)
 return wind,parity,samples,margin,cost,stopped
for x in LEVELS:
 s=(0,0,(),0,0,None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=AVIARY
  for i in range(8):x=8+(i%4)*12;y=8+(i//4)*13;f[y:y+9,x:x+9]=WIND;f[y+2:y+7,x+2:x+7]=FLOCK if i==g.wind else PARITY
  for i,(_,p,sign) in enumerate(g.samples[-5:]):x=8+i*10;f[36:42,x:x+7]=SAMPLE if sign>0 else PARITY;f[43:46,x:x+2+p*3]=FLOCK
  center=31;lo=max(5,min(center,center+g.margin));hi=min(58,max(center,center+g.margin));f[50:55,lo:hi+1]=MARGIN
  if g.stopped:f[52:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q693(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q693",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.wind=self.parity=self.margin=self.cost=0;self.samples=();self.stopped=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.wind,self.parity,self.samples,self.margin,self.cost,self.stopped=advance((self.wind,self.parity,self.samples,self.margin,self.cost,self.stopped),a)
  elif a==6:
   if (self.wind,self.parity,self.samples,self.margin,self.cost,self.stopped)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
