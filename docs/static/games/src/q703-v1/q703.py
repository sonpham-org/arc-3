"""q703 Impeller Evidence -- stop sampling before certainty makes further wake probes costly."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FIELD,SAMPLE0,SAMPLE1,SAMPLE2,BLADE,MARGIN,WAKE,COST,GOAL,BAD=6,0,11,9,12,14,10,7,5,13,15
LEVELS=[
 {"name":"Certain Blade","budget":1,"seq":(1,)},{"name":"Negative Pair","budget":2,"seq":(2,2)},
 {"name":"Early Certainty","budget":3,"seq":(1,1)},{"name":"Unequal Wakes","budget":4,"seq":(1,3,1)},
 {"name":"Sample Budget","budget":5,"seq":(2,2,3,2)},
 {"name":"Impeller Evidence","budget":6,"seq":(1,3,1,4,2)}]
WEIGHTS=(3,-2,1)
def advance(s,a,x):
 margin,used,wake,samples,cost,stopped=s
 if a in (1,2,3):
  if used>=x["budget"]:return None
  decisive=abs(margin)>(x["budget"]-used)*3;w=WEIGHTS[a-1]*(1 if wake==0 else -1);margin+=w;used+=1;samples=samples+(w,);cost+=2 if decisive else 1
 elif a==4:wake^=1
 elif a==5:
  if abs(margin)<=(x["budget"]-used)*3 or cost>used:return None
  stopped=(1 if margin>0 else -1,margin,used,wake,cost)
 return margin,used,wake,samples,cost,stopped
for x in LEVELS:
 s=(0,0,0,(),0,None)
 for a in x["seq"]:s=advance(s,a,x);assert s is not None
 assert abs(s[0])>(x["budget"]-s[1])*3 and s[4]==s[1];x["plan"]=x["seq"]+(5,)
def target(x):
 s=(0,0,0,(),0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=FIELD;cols=(SAMPLE0,SAMPLE1,SAMPLE2)
  for i in range(g.cfg["budget"]):f[9:16,8+i*8:13+i*8]=BLADE if i>=g.used else cols[i%3]
  for i,w in enumerate(g.samples[-6:]):f[23:31,8+i*8:14+i*8]=SAMPLE0 if w>1 else SAMPLE1 if w<0 else SAMPLE2
  for i,c in enumerate(cols):f[34:37,8+i*12:17+i*12]=c
  center=32;width=min(abs(g.margin),12)*2
  if g.margin>=0:f[40:45,center:center+width]=MARGIN
  else:f[40:45,center-width:center]=SAMPLE1
  f[49:53,8:8+g.wake*22+16]=WAKE;f[55:59,8:8+min(g.cost,9)*5]=COST
  if g.stopped:f[55:59,43:56]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q703(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q703",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.margin=self.used=self.wake=self.cost=0;self.samples=();self.stopped=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.margin,self.used,self.wake,self.samples,self.cost,self.stopped),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.margin,self.used,self.wake,self.samples,self.cost,self.stopped=s
  elif a==6:
   if (self.margin,self.used,self.wake,self.samples,self.cost,self.stopped)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
