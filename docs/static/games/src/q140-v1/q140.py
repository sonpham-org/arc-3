"""q140 Grounded Labels -- invent reusable markers that autonomous workers obey."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,YARD,WORKER,OBJECT,LABEL,CLASS,OUTPUT,GOAL,BAD=2,10,9,14,6,4,11,7,15
def make(classes,mapping):
 seen={};p=[]
 for c in classes:
  if c not in seen:seen[c]=mapping[c];p.append(mapping[c])
  p.append(4)
 return tuple(p)+(5,)
LEVELS=[{"name":"One Class","classes":(0,0),"mapping":(1,2,3),"plan":make((0,0),(1,2,3))},{"name":"Two Classes","classes":(0,1,0),"mapping":(2,1,3),"plan":make((0,1,0),(2,1,3))},{"name":"Reusable Mark","classes":(2,0,2,1),"mapping":(3,1,2),"plan":make((2,0,2,1),(3,1,2))},{"name":"Worker Relay","classes":(1,2,0,1,2),"mapping":(2,3,1),"plan":make((1,2,0,1,2),(2,3,1))},{"name":"Crossed Labels","classes":(2,1,2,0,1,0),"mapping":(1,3,2),"plan":make((2,1,2,0,1,0),(1,3,2))},{"name":"Grounded Labels","classes":(0,2,1,0,1,2,0),"mapping":(3,2,1),"plan":make((0,2,1,0,1,2,0),(3,2,1))}]
def advance(s,a,x):
 labels,index,outputs,sealed=s;labels=list(labels);outputs=list(outputs)
 if a in (1,2,3):
  if index>=len(x["classes"]):return None
  labels[x["classes"][index]]=a
 elif a==4:
  if index>=len(x["classes"]) or not labels[x["classes"][index]]:return None
  c=x["classes"][index];outputs.append((c,labels[c]));index+=1
 elif a==5:
  if index!=len(x["classes"]):return None
  sealed=(tuple(labels),tuple(outputs))
 return tuple(labels),index,tuple(outputs),sealed
def target(x):
 s=((0,0,0),0,(),None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=YARD
  for i,v in enumerate(g.labels):x=8+i*18;f[8:30,x:x+14]=CLASS;f[20:26,x+4:x+10]=LABEL-v if v else OBJECT-i
  for i,(_,v) in enumerate(g.outputs[-8:]):x=8+(i%4)*12;y=35+(i//4)*9;f[y:y+6,x:x+8]=OUTPUT-v
  f[53:56,8:24]=WORKER;f[56:59,44:56]=GOAL
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q140(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q140",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.labels=(0,0,0);self.index=0;self.outputs=();self.sealed=None
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.labels,self.index,self.outputs,self.sealed),a,x)
   if s is None:self.bad=True;self.lose()
   else:self.labels,self.index,self.outputs,self.sealed=s
  elif a==6:
   if (self.labels,self.index,self.outputs,self.sealed)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
