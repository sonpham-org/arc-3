"""q692 Lockwater Evidence -- combine unequal canal samples while barge identity moves."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,CANAL,BARGE,WATER,IDENTITY,SAMPLE,MARGIN,GOAL,BAD=6,11,14,10,8,9,12,13,15
LEVELS=[
 {"name":"One Reading","seq":(1,)},{"name":"Unequal Gauge","seq":(2,1)},
 {"name":"Moving Identity","seq":(3,1,2)},{"name":"Coupled Margin","seq":(1,3,2,1)},
 {"name":"Enough Evidence","seq":(2,3,1,2,3,1)},
 {"name":"Lockwater Evidence","seq":(1,2,3,1,3,2,1,2,3)}]
def advance(s,a):
 identities,levels,samples,margin,cost,stopped=s;i=list(identities);w=list(levels)
 if a==1:margin+=w[0]+1;samples=samples+((i[0],w[0],1),);cost+=1
 elif a==2:margin-=max(1,w[1]-1);samples=samples+((i[1],w[1],-1),);cost+=2
 elif a==3:i[0],i[1]=i[1],i[0];w=w[1:]+w[:1];margin+=i[0]-i[1]
 elif a==4:w=[(v+1)%5 for v in w];cost+=1
 elif a==5:stopped=(tuple(i),tuple(w),samples[-4:],margin,cost)
 return tuple(i),tuple(w),samples,margin,cost,stopped
for x in LEVELS:
 s=((0,1,2),(1,3,2),(),0,0,None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=CANAL
  for slot,(identity,level) in enumerate(zip(g.identities,g.levels)):
   x=8+slot*17;f[9:31,x:x+13]=WATER;f[26-level*4:30,x+2:x+11]=BARGE;f[33+identity:36+identity,x:x+13]=IDENTITY
  for j,(_,v,sign) in enumerate(g.samples[-5:]):x=8+j*10;f[41:46,x:x+7]=SAMPLE if sign>0 else MARGIN;f[47:49,x:x+2+v]=WATER
  center=31;lo=min(center,center+g.margin);hi=max(center,center+g.margin);f[52:56,lo:hi+1]=MARGIN
  if g.stopped:f[52:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q692(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"]
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q692",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.identities=(0,1,2);self.levels=(1,3,2);self.samples=();self.margin=self.cost=0;self.stopped=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.identities,self.levels,self.samples,self.margin,self.cost,self.stopped=advance((self.identities,self.levels,self.samples,self.margin,self.cost,self.stopped),a)
  elif a==6:
   if (self.identities,self.levels,self.samples,self.margin,self.cost,self.stopped)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
