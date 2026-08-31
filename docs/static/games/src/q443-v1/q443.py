"""q443 Ember Lineage -- trace vessel ancestry while every transformation burns shared fuel."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,KILN,HEAT,VESSEL,TRAIL,SELECT,RESOURCE,GATE,BAD=3,9,8,14,12,5,11,7,15
LEVELS=[{"name":"First Split","fuel":4,"ancestor":1,"plan":(1,4,5)},{"name":"Appearance Heat","fuel":7,"ancestor":2,"plan":(3,1,4,2,4,5)},{"name":"Merged Vessel","fuel":8,"ancestor":3,"plan":(1,2,3,4,4,4,5)},{"name":"Fuel Gate","fuel":8,"ancestor":2,"plan":(3,1,4,2,1,4,5)},{"name":"Causal Ember","fuel":6,"ancestor":1,"plan":(1,3,2,4,5)},{"name":"Ember Lineage","fuel":10,"ancestor":3,"plan":(3,1,2,4,3,4,1,4,5)}]
def advance(s,a):
 tokens,heat,selection,resource,committed=s;t=[list(x) for x in tokens]
 if resource<=0 or committed:return None
 if a==1:
  m,c=t.pop(0);t.extend([[m,(c+1+heat)%4],[m,(c+2)%4]])
 elif a==2 and len(t)>=2:
  p=t.pop(0);q=t.pop(0);t.insert(0,[p[0]|q[0],(p[1]+q[1]+heat)%4])
 elif a==3:
  colors=[x[1] for x in t][1:]+[t[0][1]]
  for x,c in zip(t,colors):x[1]=c
 elif a==4:heat=(heat+1)%4;t.reverse();selection=(selection+1)%4
 elif a==5:committed=True
 resource-=1
 return tuple((x[0],x[1]) for x in t),heat,selection,resource,committed
def target(x):
 s=(((1,0),(2,1),(4,2)),0,0,x["fuel"],False)
 for a in x["plan"]:s=advance(s,a);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;x=LEVELS[g.level_index];f[:,:]=BG;f[4:60,4:60]=KILN;f[8:15,8:56]=HEAT
  for i,(mask,color) in enumerate(g.tokens):px=6+i*11;f[20:31,px:px+9]=VESSEL-color%3;f[34:37,px:px+min(mask,7)*2]=TRAIL
  f[44:47,8:11+g.selection*12]=SELECT;f[50:53,8:11+x["ancestor"]*12]=GATE;f[55:58,8:11+g.resource*4]=RESOURCE;f[58:60,49:56]=GATE if g.committed else HEAT
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q443(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset(LEVELS[0]);self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q443",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self,x):self.tokens=((1,0),(2,1),(4,2));self.heat=self.selection=0;self.resource=x["fuel"];self.committed=False
 def on_set_level(self,l):x=LEVELS[self.level_index];self._reset(x);self.bad=False;self.target=target(x)
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.tokens,self.heat,self.selection,self.resource,self.committed),a)
   if s is None:self.bad=True;self.lose()
   else:self.tokens,self.heat,self.selection,self.resource,self.committed=s
  elif a==6:
   if (self.tokens,self.heat,self.selection,self.resource,self.committed)==self.target and self.selection==x["ancestor"]:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
