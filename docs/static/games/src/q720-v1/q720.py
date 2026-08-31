"""q720 Spore Gradient -- conserve a distribution across unequal actor schedules."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,GREENHOUSE,GLASS,SPORE,HUMID,CLOCK,PHASE,COMMIT,BAD=8,12,11,6,2,9,4,13,15
LEVELS=[
 {"name":"Twin Distribution","cycles":(2,2),"phase_step":False},{"name":"Unequal Distribution","cycles":(3,2),"phase_step":False},
 {"name":"Triple Distribution","cycles":(3,3),"phase_step":True},{"name":"Sparse Gradient","cycles":(4,3),"phase_step":True},
 {"name":"Long Gradient","cycles":(5,4),"phase_step":True},{"name":"Spore Gradient","cycles":(6,5),"phase_step":True}]
for x in LEVELS:
 a,b=x["cycles"];x["initial"]=(a,0,0);x["threshold"]=2*a+b+int(x["phase_step"]);x["plan"]=(1,)*a+(2,)*b+(3,)*int(x["phase_step"])+(4,5)
def influence(bins,phase):return bins[0]+2*bins[1]+3*bins[2]+phase
def advance(s,a,x):
 bins,clocks,phase,observed,committed=s;bins=list(bins);clocks=list(clocks)
 if committed is not None:return None
 if a==1:
  if bins[0]<=0:return None
  bins[0]-=1;bins[1]+=1;clocks[0]=(clocks[0]+1)%x["cycles"][0]
 elif a==2:
  if bins[1]<=0:return None
  bins[1]-=1;bins[2]+=1;clocks[1]=(clocks[1]+1)%x["cycles"][1]
 elif a==3:phase=(phase+1)%4
 elif a==4:
  if tuple(clocks)!=(0,0):return None
  observed=influence(bins,phase)
 elif a==5:
  now=influence(bins,phase)
  if observed!=now or now<x["threshold"]:return None
  committed=(tuple(bins),tuple(clocks),phase,now)
 return tuple(bins),tuple(clocks),phase,observed,committed
def target(x):
 s=(x["initial"],(0,0),0,None,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=GREENHOUSE
  for i,v in enumerate(g.bins):x=8+i*17;f[8:35,x:x+13]=GLASS+i%2;f[31-v*4:33,x+2:x+11]=SPORE+i
  f[40:44,8:8+g.clocks[0]*8]=CLOCK;f[46:50,8:8+g.clocks[1]*7]=CLOCK+2;f[53:56,8:8+g.phase*11]=PHASE
  if g.observed is not None:f[57:60,8:56]=HUMID
  if g.committed:f[38:58,56:59]=COMMIT
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q720(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q720",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.bins=self.cfg["initial"];self.clocks=(0,0);self.phase=0;self.observed=self.committed=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.bins,self.clocks,self.phase,self.observed,self.committed),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.bins,self.clocks,self.phase,self.observed,self.committed=s
  elif a==6:
   if (self.bins,self.clocks,self.phase,self.observed,self.committed)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
